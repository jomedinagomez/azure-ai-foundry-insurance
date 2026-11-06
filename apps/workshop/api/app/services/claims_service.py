"""Local claim evidence explorer and explicit notebook-equivalent processing."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any

import extract_msg
import tiktoken
from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import AnalysisInput
from azure.core.exceptions import ResourceNotFoundError
from azure.core.serialization import AzureJSONEncoder
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration, HnswParameters, SearchField, SearchFieldDataType,
    SearchIndex, SemanticConfiguration, SemanticField, SemanticPrioritizedFields,
    SemanticSearch, VectorSearch, VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery
from extract_msg.msg_classes import MSGFile
from langchain_text_splitters import MarkdownHeaderTextSplitter
from openai import OpenAI

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[5]
CLAIMS = ROOT / "data" / "claims"
COLUMNS = [
    "id", "claim_id", "document_hash", "chunk_id", "title", "header", "content",
    "source_type", "content_kind", "filename", "source_path", "source_files",
    "parent_emails", "figure_id", "source_region", "analyzer_id",
    "analyzer_api_version", "content_vector",
]
STAGES = ["files", "extract", "chunks", "embed", "index"]
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="claims")
_run_lock = threading.Lock()
_state_lock = threading.Lock()
_artifact_lock = threading.RLock()
_job: dict[str, Any] | None = None


def output_root() -> Path:
    return (ROOT / os.getenv("CLAIMS_OUTPUT_ROOT", r"output\claims")).resolve()


def claim_path(claim_id: str) -> Path:
    if not re.fullmatch(r"claim-[a-zA-Z0-9-]+", claim_id):
        raise ValueError("Invalid claim folder identifier.")
    path = (CLAIMS / claim_id).resolve()
    if path.parent != CLAIMS.resolve() or not path.is_dir() or path.is_symlink():
        raise FileNotFoundError("Claim folder not found.")
    return path


def _read(path: Path) -> Any:
    with _artifact_lock:
        return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, cls=AzureJSONEncoder, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    # This local Windows workspace permits writes but not replace-over-existing.
    with _artifact_lock:
        path.write_text(serialized, encoding="utf-8")


def _dimensions() -> int:
    value = int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "3072"))
    if value < 1:
        raise ValueError("Embedding dimensions must be positive.")
    return value


def _setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Configure {name} in the repository .env, then restart the API.")
    return value


def _deployment() -> str:
    return os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or _setting("EMBEDDING_MODEL_DEPLOYMENT")


def _openai_endpoint() -> str:
    return (os.getenv("AZURE_OPENAI_ENDPOINT") or _setting("APP_CONTENT_UNDERSTANDING_ENDPOINT")
            .replace(".cognitiveservices.azure.com", ".openai.azure.com")
            .replace(".services.ai.azure.com", ".openai.azure.com")).rstrip("/")


@dataclass
class Evidence:
    document_hash: str
    filename: str
    source_type: str
    source_path: str
    data: bytes = b""
    text: str = ""
    source_files: list[str] = field(default_factory=list)
    parent_emails: list[str] = field(default_factory=list)


def inventory(claim_id: str) -> tuple[dict[str, Evidence], list[dict[str, str]], int]:
    folder = claim_path(claim_id)
    items: dict[str, Evidence] = {}
    skipped: list[dict[str, str]] = []
    paths = sorted(path for path in folder.rglob("*") if path.is_file())
    if not paths:
        raise ValueError("The claim folder is empty.")
    for path in paths:
        if not path.resolve().is_relative_to(folder) or path.is_symlink():
            raise ValueError("Claim inputs must not link outside their folder.")

    def add_visual(data: bytes, filename: str, source: str, parent: str = "") -> None:
        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
            raise ValueError(f"Unsupported evidence: {source}")
        if filename.casefold() == "email-signature.png":
            skipped.append({"source": source, "reason": "Fixture signature / branding"})
            return
        key = hashlib.sha256(data).hexdigest()
        destination = output_root() / claim_id / "attachments" / f"{key}{suffix}"
        original = folder.joinpath(*PureWindowsPath(source).parts[1:])
        item = items.setdefault(key, Evidence(
            key, filename, "document" if suffix == ".pdf" else "image",
            str(destination if parent else original), data=data,
        ))
        item.source_files.append(source)
        if parent and parent not in item.parent_emails:
            item.parent_emails.append(parent)

    def read_message(message: MSGFile, source: str, parent: str = "", depth: int = 0) -> None:
        if depth > 12:
            raise ValueError("Nested email depth exceeds 12; inspect this message manually.")
        if message.body is None and message.htmlBody:
            raise ValueError(f"MSG has no parsed text body: {source}")
        headers = {"subject": message.subject or "", "sender": message.sender or "",
                   "to": message.to or "", "date": str(message.date)}
        body = (message.body or "").replace("\r\n", "\n")
        key = hashlib.sha256(json.dumps({**headers, "body": body}, sort_keys=True).encode()).hexdigest()
        original = folder.joinpath(*PureWindowsPath(source.split("::", 1)[0]).parts[1:])
        item = items.setdefault(key, Evidence(
            key, PureWindowsPath(source.rsplit("::", 1)[-1]).name, "email", str(original),
            text="# " + headers["subject"] + "\n\n"
                 + "\n".join(f"{name}: {value}" for name, value in headers.items()) + "\n\n" + body,
        ))
        seen = bool(item.source_files)
        item.source_files.append(source)
        if parent and parent not in item.parent_emails:
            item.parent_emails.append(parent)
        if seen:
            return
        for number, attachment in enumerate(message.attachments):
            name = PureWindowsPath(str(attachment.getFilename() or f"attachment-{number}")).name
            data = attachment.data
            if isinstance(data, MSGFile):
                read_message(data, f"{source}::{name}", key, depth + 1)
            elif isinstance(data, bytes):
                add_visual(data, name, f"{source}::{name}", key)
            else:
                raise ValueError(f"Unsupported attachment data: {source}::{name}")

    for path in paths:
        source = f"{claim_id}/{path.relative_to(folder).as_posix()}"
        if path.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png"}:
            add_visual(path.read_bytes(), path.name, source)
        elif path.suffix.lower() != ".msg":
            raise ValueError(f"Unsupported input in claim folder: {path.name}")
    for path in paths:
        if path.suffix.lower() == ".msg":
            with extract_msg.openMsg(str(path)) as message:
                read_message(message, f"{claim_id}/{path.relative_to(folder).as_posix()}")
    return items, skipped, len(paths)


def _route(item: Evidence, document_images: set[str]) -> str:
    if item.source_type == "email":
        return "local-msg"
    return ("prebuilt-documentSearch" if item.source_type == "document" or item.filename in document_images
            else "prebuilt-imageSearch")


def _cache_path(item: Evidence, analyzer: str) -> Path:
    return output_root() / "cu-results" / f"{analyzer}_{os.getenv('CU_API_VERSION', '2025-11-01')}_{item.document_hash}.json"


def _records(claim_id: str) -> list[dict[str, Any]]:
    path = output_root() / claim_id / "processed-evidence-v1.json"
    if not path.exists():
        return []
    records = _read(path)
    if not isinstance(records, list) or any(
        not isinstance(row, dict) or set(row) != set(COLUMNS) or row["claim_id"] != claim_id
        for row in records
    ):
        raise ValueError(f"Invalid evidence schema in {path.name}; regenerate it with notebook 1.")
    if any(not isinstance(row["content_vector"], list) or
           any(type(value) not in (int, float) or not math.isfinite(value) for value in row["content_vector"])
           for row in records):
        raise ValueError(f"Invalid embedding values in {path.name}; regenerate the prepared records.")
    return records


def _public_chunk(row: dict[str, Any]) -> dict[str, Any]:
    return {**{key: value for key, value in row.items() if key != "content_vector"},
            "vector_dimensions": len(row["content_vector"])}


def claim_detail(claim_id: str) -> dict[str, Any]:
    items, skipped, original_count = inventory(claim_id)
    records = _records(claim_id)
    current = [row for row in records if row["document_hash"] in items]
    stale = len(records) - len(current)
    receipt_path = output_root() / claim_id / "upload-results.json"
    receipts = _read(receipt_path) if receipt_path.exists() else []
    uploaded_ids = {row["id"] for row in receipts if row.get("succeeded")}
    files = []
    for key, item in items.items():
        chunks = [row for row in current if row["document_hash"] == key]
        analyzer = chunks[0]["analyzer_id"] if chunks else _route(item, set())
        cached = analyzer == "local-msg" or _cache_path(item, analyzer).exists()
        files.append({
            "id": key, "filename": item.filename, "source_type": item.source_type,
            "source_files": item.source_files, "parent_emails": item.parent_emails,
            "bytes": len(item.data) if item.data else len(item.text.encode()),
            "analyzer_id": analyzer, "extracted": cached, "chunks": len(chunks),
            "embedded": bool(chunks) and all(len(row["content_vector"]) == _dimensions() for row in chunks),
            "uploaded": bool(chunks) and all(row["id"] in uploaded_ids for row in chunks),
            "text": item.text, "attachment_only": all("::" in source for source in item.source_files),
        })
    stages = {
        "files": True, "extract": all(file["extracted"] for file in files),
        "chunks": bool(current) and {row["document_hash"] for row in current} == set(items) and not stale,
        "embed": bool(current) and all(file["embedded"] for file in files) and not stale,
        "index": bool(current) and all(file["uploaded"] for file in files) and not stale,
    }
    return {"claim_id": claim_id, "original_files": original_count, "files": files,
            "chunks": [_public_chunk(row) for row in current], "stages": stages,
            "skipped": skipped, "stale_chunks": stale,
            "duplicate_occurrences": sum(len(item.source_files) - 1 for item in items.values())}


def list_claims() -> dict[str, Any]:
    summaries = []
    for folder in sorted(CLAIMS.glob("claim-*")):
        if not folder.is_dir():
            continue
        detail = claim_detail(folder.name)
        image = next((item["id"] for item in detail["files"]
                      if item["source_type"] == "image" and not item["attachment_only"]), None)
        summaries.append({
            "claim_id": folder.name, "original_files": detail["original_files"],
            "evidence_files": len(detail["files"]), "chunks": len(detail["chunks"]),
            "stages": detail["stages"], "cover_id": image, "stale_chunks": detail["stale_chunks"],
        })
    return {"claims": summaries, "index_name": os.getenv("AZURE_SEARCH_INDEX_NAME", "claims-evidence-v1"),
            "output_root": str(output_root()), "job": active_job()}


def file_detail(claim_id: str, evidence_id: str) -> dict[str, Any]:
    detail = claim_detail(claim_id)
    item = next((item for item in detail["files"] if item["id"] == evidence_id), None)
    if item is None:
        raise FileNotFoundError("Evidence file not found.")
    native = ""
    evidence = inventory(claim_id)[0][evidence_id]
    cache = _cache_path(evidence, item["analyzer_id"])
    if cache.exists():
        result = _read(cache)
        native = "\n\n".join(
            (content.get("fields") or {}).get("Summary", {}).get("valueString", "")
            if item["analyzer_id"] == "prebuilt-imageSearch" else content.get("markdown") or ""
            for content in result.get("contents", [])
        )
    return {"file": item, "native_text": native,
            "chunks": [row for row in detail["chunks"] if row["document_hash"] == evidence_id]}


def raw_file(claim_id: str, evidence_id: str) -> Evidence:
    item = inventory(claim_id)[0].get(evidence_id)
    if item is None or item.source_type == "email":
        raise FileNotFoundError("Preview file not found.")
    return item


def _chunk_rows(claim_id: str, items: dict[str, Evidence], results: dict[str, Any],
                routes: dict[str, str]) -> list[dict[str, Any]]:
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "Title"), ("##", "Header 1")], strip_headers=False)
    rows: list[dict[str, Any]] = []
    for key, item in items.items():
        base = {"claim_id": claim_id, "document_hash": key, "filename": item.filename,
                "source_type": item.source_type, "source_path": item.source_path,
                "source_files": item.source_files, "parent_emails": item.parent_emails,
                "analyzer_id": routes[key], "analyzer_api_version": os.getenv("CU_API_VERSION", "2025-11-01")
                if item.source_type != "email" else ""}
        start = len(rows)

        def append_text(text: str, kind: str) -> None:
            for chunk in splitter.split_text(text):
                rows.append({**base, "title": chunk.metadata.get("Title") or item.filename,
                             "header": chunk.metadata.get("Header 1", ""), "content": chunk.page_content,
                             "content_kind": kind, "figure_id": "", "source_region": ""})

        if item.source_type == "email":
            append_text(item.text, "email_text")
        else:
            for content in results[key]["contents"]:
                if routes[key] == "prebuilt-imageSearch":
                    observation = (content.get("fields") or {}).get("Summary", {}).get("valueString", "")
                    if not observation.strip():
                        raise ValueError(f"No native image summary for {item.filename}.")
                    rows.append({**base, "title": item.filename,
                                 "header": "Visual observation; not a causation or coverage finding",
                                 "content": observation, "content_kind": "image_description",
                                 "figure_id": "", "source_region": ""})
                else:
                    append_text(content.get("markdown") or "", "document_text")
                    for figure in content.get("figures") or []:
                        if figure.get("description"):
                            rows.append({**base, "title": item.filename,
                                         "header": f"CU figure {figure['id']} description",
                                         "content": figure["description"], "content_kind": "figure_description",
                                         "figure_id": figure["id"], "source_region": figure.get("source") or ""})
        if len(rows) == start:
            raise ValueError(f"No searchable evidence extracted from {item.filename}; review its analyzer route.")
        for number, row in enumerate(rows[start:], start=1):
            row["chunk_id"] = number
            row["id"] = hashlib.sha256(f"{claim_id}:{key}:{number}".encode()).hexdigest()
    return rows


def _embedding_text(row: dict[str, Any]) -> str:
    return "\n\n".join([f"Title: {row['title']}", f"Section: {row['header']}",
                       f"Evidence kind: {row['content_kind']}", row["content"]])


def _index() -> SearchIndex:
    string = SearchFieldDataType.String
    fields = [
        SearchField(name="id", type=string, key=True, filterable=True),
        SearchField(name="claim_id", type=string, filterable=True),
        SearchField(name="document_hash", type=string, filterable=True),
        SearchField(name="chunk_id", type=SearchFieldDataType.Int32, sortable=True),
        *[SearchField(name=name, type=string, searchable=True) for name in ["title", "header", "content"]],
        *[SearchField(name=name, type=string, filterable=True, facetable=True) for name in ["source_type", "content_kind"]],
        SearchField(name="filename", type=string, searchable=True, filterable=True),
        SearchField(name="source_path", type=string),
        SearchField(name="source_files", type=SearchFieldDataType.Collection(string)),
        SearchField(name="parent_emails", type=SearchFieldDataType.Collection(string), filterable=True),
        SearchField(name="figure_id", type=string, filterable=True),
        SearchField(name="source_region", type=string),
        SearchField(name="analyzer_id", type=string, filterable=True, facetable=True),
        SearchField(name="analyzer_api_version", type=string, filterable=True),
        SearchField(name="content_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, hidden=True, vector_search_dimensions=_dimensions(),
                    vector_search_profile_name="claims-content-profile"),
    ]
    for item in fields:
        for attribute in ["key", "hidden", "searchable", "filterable", "facetable", "sortable"]:
            setattr(item, attribute, bool(getattr(item, attribute)))
    return SearchIndex(
        name=os.getenv("AZURE_SEARCH_INDEX_NAME", "claims-evidence-v1"),
        fields=fields,
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="claims-hnsw", parameters=HnswParameters(metric="cosine"))],
            profiles=[VectorSearchProfile(name="claims-content-profile", algorithm_configuration_name="claims-hnsw")]),
        semantic_search=SemanticSearch(default_configuration_name="claims-semantic", configurations=[
            SemanticConfiguration(name="claims-semantic", prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content"), SemanticField(field_name="header")]))]),
    )


def _ensure_index(credential: DefaultAzureCredential) -> None:
    expected = _index()
    with SearchIndexClient(endpoint=_setting("AZURE_SEARCH_SERVICE_ENDPOINT"), credential=credential) as client:
        try:
            existing = client.get_index(expected.name)
        except ResourceNotFoundError:
            client.create_index(expected)
            return
    actual = {item.name: item for item in existing.fields}
    if set(actual) != set(COLUMNS):
        raise ValueError("Existing index has different evidence fields. Choose a new index name; nothing was replaced.")
    for item in expected.fields:
        for attribute in ["type", "vector_search_dimensions", "vector_search_profile_name"]:
            if getattr(actual[item.name], attribute) != getattr(item, attribute):
                raise ValueError(f"Incompatible index field {item.name}.{attribute}; nothing was replaced.")
        for attribute in ["key", "hidden", "searchable", "filterable", "facetable", "sortable"]:
            if bool(getattr(actual[item.name], attribute)) != bool(getattr(item, attribute)):
                raise ValueError(f"Incompatible index field {item.name}.{attribute}; nothing was replaced.")
    profiles = existing.vector_search.profiles if existing.vector_search else []
    algorithms = existing.vector_search.algorithms if existing.vector_search else []
    if not any(item.name == "claims-content-profile" and item.algorithm_configuration_name == "claims-hnsw" for item in profiles or []):
        raise ValueError("The claims content-vector profile is missing; nothing was replaced.")
    if not any(item.name == "claims-hnsw" and item.kind == "hnsw" and item.parameters
               and item.parameters.metric == "cosine" for item in algorithms or []):
        raise ValueError("The claims HNSW/cosine configuration differs; nothing was replaced.")
    configurations = existing.semantic_search.configurations if existing.semantic_search else []
    semantic = next((item for item in configurations or [] if item.name == "claims-semantic"), None)
    prioritized = semantic.prioritized_fields if semantic else None
    if not prioritized or not prioritized.title_field or prioritized.title_field.field_name != "title" or [
        item.field_name for item in prioritized.content_fields or []
    ] != ["content", "header"]:
        raise ValueError("The claims semantic configuration differs; nothing was replaced.")


def _filter(claim_id: str) -> str:
    return "claim_id eq '" + claim_id.replace("'", "''") + "'"


def _upload(claim_id: str, rows: list[dict[str, Any]], credential: DefaultAzureCredential) -> None:
    _ensure_index(credential)
    with SearchClient(endpoint=_setting("AZURE_SEARCH_SERVICE_ENDPOINT"),
                      index_name=_index().name, credential=credential) as client:
        old_ids = {row["id"] for row in client.search(search_text="*", filter=_filter(claim_id), select=["id"])}
        receipts = []
        for start in range(0, len(rows), 100):
            batch = client.upload_documents(rows[start:start + 100])
            receipts.extend({"id": item.key, "succeeded": item.succeeded, "error": item.error_message} for item in batch)
            if len(batch) != len(rows[start:start + 100]) or any(not item.succeeded for item in batch):
                raise RuntimeError("Search rejected evidence rows; stale rows were not deleted.")
        _write(output_root() / claim_id / "upload-results.json", receipts)
        new_ids = {row["id"] for row in rows}
        stale = old_ids - new_ids
        for start in range(0, len(stale), 100):
            batch = client.delete_documents([{"id": key} for key in sorted(stale)[start:start + 100]])
            if len(batch) != len(sorted(stale)[start:start + 100]) or any(not item.succeeded for item in batch):
                raise RuntimeError("Search could not remove stale rows for this claim.")
        for attempt in range(12):
            visible = {row["id"] for row in client.search(search_text="*", filter=_filter(claim_id), select=["id"])}
            if visible == new_ids:
                return
            if attempt < 11:
                time.sleep(2)
        raise RuntimeError("Upload accepted, but Search visibility has not caught up. Retry indexing; extraction is cached.")


def _event(claim_id: str, stage: str, message: str, evidence_id: str = "", done: bool = False) -> None:
    with _state_lock:
        if _job is None:
            raise RuntimeError("No active claims job.")
        _job.update(claim_id=claim_id, stage=stage, message=message)
        _job["events"].append({"claim_id": claim_id, "stage": stage, "message": message,
                               "evidence_id": evidence_id, "done": done})
        _job["events"] = _job["events"][-200:]
        _write(output_root() / "app-run.json", _job)


def _process(claim_id: str, index_data: bool, document_images: set[str]) -> None:
    _event(claim_id, "files", "Reading original files and nested email attachments")
    items, _, _ = inventory(claim_id)
    if document_images - {item.filename for item in items.values() if item.source_type == "image"}:
        raise ValueError("A document-image override does not match an image in this claim.")
    routes = {key: _route(item, document_images) for key, item in items.items()}
    for item in items.values():
        if item.parent_emails and item.data:
            destination = output_root() / claim_id / "attachments" / f"{item.document_hash}{Path(item.filename).suffix.lower()}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(item.data)
    _event(claim_id, "files", f"{len(items)} unique evidence files; original aliases retained", done=True)
    results: dict[str, Any] = {}
    with DefaultAzureCredential() as credential:
        with ContentUnderstandingClient(endpoint=_setting("APP_CONTENT_UNDERSTANDING_ENDPOINT"),
                                        credential=credential, api_version=os.getenv("CU_API_VERSION", "2025-11-01")) as client:
            for key, item in items.items():
                if item.source_type == "email":
                    continue
                cache = _cache_path(item, routes[key])
                _event(claim_id, "extract", f"{'Reading saved result' if cache.exists() else 'Analyzing'}: {item.filename}", key)
                result = _read(cache) if cache.exists() else client.begin_analyze(
                    analyzer_id=routes[key], inputs=[AnalysisInput(data=item.data)]).result().as_dict()
                if not result.get("contents") or result.get("analyzerId") != routes[key] or result.get("apiVersion") != os.getenv("CU_API_VERSION", "2025-11-01"):
                    raise ValueError(f"Incompatible or empty CU result for {item.filename}.")
                _write(cache, result)
                results[key] = result
                _event(claim_id, "extract", f"Extracted {item.filename}", key, done=True)
        _event(claim_id, "extract", "Native text and image descriptions ready", done=True)
        rows = _chunk_rows(claim_id, items, results, routes)
        _event(claim_id, "chunks", f"{len(rows)} evidence chunks with source relationships", done=True)
        previous = {row["id"]: row for row in _records(claim_id)}
        encoding = tiktoken.get_encoding("cl100k_base")
        with OpenAI(base_url=f"{_openai_endpoint()}/openai/v1/",
                    api_key=get_bearer_token_provider(credential, "https://ai.azure.com/.default")) as client:
            for number, row in enumerate(rows, start=1):
                text = _embedding_text(row)
                if not text.strip() or len(encoding.encode(text, disallowed_special=())) > 8000:
                    raise ValueError(f"Oversized/empty embedding input in {row['filename']}; split it instead of truncating.")
                old = previous.get(row["id"])
                if old and _embedding_text(old) == text and len(old["content_vector"]) == _dimensions():
                    row["content_vector"] = old["content_vector"]
                else:
                    row["content_vector"] = client.embeddings.create(
                        input=text, model=_deployment(), dimensions=_dimensions()).data[0].embedding
                if len(row["content_vector"]) != _dimensions() or any(not math.isfinite(value) for value in row["content_vector"]):
                    raise ValueError("Embedding dimensions/values do not match the index.")
                _event(claim_id, "embed", f"Vector {number} of {len(rows)}", row["document_hash"])
        _write(output_root() / claim_id / "processed-evidence-v1.json", [{name: row[name] for name in COLUMNS} for row in rows])
        _event(claim_id, "embed", f"{len(rows)} full vectors saved; values are not sent to the browser", done=True)
        if index_data:
            _event(claim_id, "index", "Uploading this claim and checking Search visibility")
            _upload(claim_id, rows, credential)
            _event(claim_id, "index", f"{len(rows)} evidence chunks verified in Search", done=True)


def _run(claim_ids: list[str], index_data: bool, document_images: set[str]) -> None:
    try:
        for claim_id in claim_ids:
            _process(claim_id, index_data, document_images if len(claim_ids) == 1 else set())
        with _state_lock:
            if _job is not None:
                _job.update(status="complete", message="Selected folders completed")
                _write(output_root() / "app-run.json", _job)
    except Exception as exc:
        logger.exception("Claims pipeline failed")
        with _state_lock:
            if _job is not None:
                _job.update(status="failed", message=str(exc))
                _write(output_root() / "app-run.json", _job)
    finally:
        _run_lock.release()


def active_job() -> dict[str, Any] | None:
    with _state_lock:
        if _job is not None:
            return copy.deepcopy(_job)
    path = output_root() / "app-run.json"
    if not path.exists():
        return None
    job = _read(path)
    if job["status"] == "running":
        job.update(status="failed", message="The API restarted during this run. Saved results are retained; rerun to resume.")
    return job


def start_run(claim_ids: list[str], index_data: bool, document_images: set[str]) -> dict[str, Any]:
    global _job
    claim_ids = list(dict.fromkeys(claim_ids))
    if not claim_ids:
        raise ValueError("Select at least one claim folder.")
    for claim_id in claim_ids:
        claim_path(claim_id)
    if document_images and len(claim_ids) != 1:
        raise ValueError("Review scan overrides on a single folder before running it.")
    _setting("APP_CONTENT_UNDERSTANDING_ENDPOINT")
    _deployment()
    if index_data:
        _setting("AZURE_SEARCH_SERVICE_ENDPOINT")
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("A claims run is already active. Wait for it to finish.")
    try:
        with _state_lock:
            _job = {"id": uuid.uuid4().hex, "status": "running", "claim_ids": claim_ids,
                    "claim_id": claim_ids[0], "stage": "files", "message": "Starting",
                    "index_data": index_data, "events": []}
            _write(output_root() / "app-run.json", _job)
        _executor.submit(_run, claim_ids, index_data, document_images)
    except Exception:
        _run_lock.release()
        raise
    job = active_job()
    if job is None:
        raise RuntimeError("The claims run did not initialize.")
    return job


def search(claim_id: str, question: str) -> list[dict[str, Any]]:
    claim_path(claim_id)
    question = question.strip()
    if not question or len(tiktoken.get_encoding("cl100k_base").encode(question, disallowed_special=())) > 8000:
        raise ValueError("Enter a nonempty question of at most 8000 tokens.")
    with DefaultAzureCredential() as credential:
        with OpenAI(base_url=f"{_openai_endpoint()}/openai/v1/",
                    api_key=get_bearer_token_provider(credential, "https://ai.azure.com/.default")) as client:
            vector = client.embeddings.create(input=question, model=_deployment(), dimensions=_dimensions()).data[0].embedding
        if len(vector) != _dimensions() or any(not math.isfinite(value) for value in vector):
            raise ValueError("Query embedding does not match the index.")
        with SearchClient(endpoint=_setting("AZURE_SEARCH_SERVICE_ENDPOINT"), index_name=_index().name, credential=credential) as client:
            rows = list(client.search(
                search_text=question, search_fields=["title", "header", "content", "filename"],
                vector_queries=[VectorizedQuery(vector=vector, fields="content_vector", k_nearest_neighbors=50)],
                filter=_filter(claim_id), vector_filter_mode="preFilter", query_type="semantic",
                semantic_configuration_name="claims-semantic", semantic_error_mode="fail",
                query_caption="extractive", query_caption_highlight_enabled=False,
                select=[name for name in COLUMNS if name != "content_vector"], top=5,
            ))
    if any(row["claim_id"] != claim_id or row.get("@search.reranker_score") is None for row in rows):
        raise RuntimeError("Semantic reranking or the selected-claim filter was not applied.")
    return [{**{name: row[name] for name in COLUMNS if name != "content_vector"},
             "score": row["@search.score"], "semantic_score": row["@search.reranker_score"],
             "caption": "\n".join(caption.text for caption in row.get("@search.captions") or [])} for row in rows]
