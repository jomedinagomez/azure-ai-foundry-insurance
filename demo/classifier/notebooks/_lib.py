"""Shared helpers for the Document Intelligence custom-classifier demo.

Keeps the notebooks thin: client construction, endpoint/credential resolution,
path discovery, blob upload, and result formatting all live here. The SDK calls
that matter for learning (build classifier, classify document) stay visible in
the notebooks themselves.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Paths — resolve the repo root (holds requirements.txt + data/) by walking up
# from this file, so notebooks work regardless of the kernel's working dir.
# --------------------------------------------------------------------------
LIB_DIR = Path(__file__).resolve().parent            # demo/classifier/notebooks
DEMO_ROOT = LIB_DIR.parent                           # demo/classifier


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "requirements.txt").exists() and (candidate / "data").is_dir():
            return candidate
    return start.parents[2] if len(start.parents) >= 3 else start


REPO_ROOT = _find_repo_root(LIB_DIR)
DATA_DIR = REPO_ROOT / "data"
INVOICES_DIR = DATA_DIR / "invoices"
CLAIMS_DIR = DATA_DIR / "propertyclaims"
REFERENCE_DIR = DEMO_ROOT / "reference"
SAMPLE_OUTPUT_DIR = REFERENCE_DIR / "sample-output"

# --------------------------------------------------------------------------
# Env — repo-root .env first (Terraform-generated), then demo .env overrides.
# Exposed as a function so a .env created *after* the kernel started can be
# reloaded without restarting the kernel.
# --------------------------------------------------------------------------
def load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(DEMO_ROOT / ".env", override=True)


load_env()

# --------------------------------------------------------------------------
# Config (env with sensible defaults; call-time env reads where it matters).
# --------------------------------------------------------------------------
CONTAINER = os.environ.get("CLASSIFIER_TRAINING_CONTAINER", "classifier-training")
CLASSIFIER_ID = os.environ.get("CLASSIFIER_ID", "insurance-invoice-claim-v1")

# Class label -> local source folder. The label becomes the blob prefix and the
# classifier docType.
CLASS_DIRS = {
    "invoice": INVOICES_DIR,
    "claim": CLAIMS_DIR,
}


# --------------------------------------------------------------------------
# Endpoint + credential resolution
# --------------------------------------------------------------------------
def resolve_endpoint() -> str:
    """Return the Document Intelligence endpoint.

    Order: DOCUMENTINTELLIGENCE_ENDPOINT -> a cognitiveservices FOUNDRY_ENDPOINT
    -> derived from FOUNDRY_RESOURCE_NAME -> FOUNDRY_ENDPOINT as-is.
    The DI data-plane SDK expects the https://<name>.cognitiveservices.azure.com/ host.
    """
    explicit = os.environ.get("DOCUMENTINTELLIGENCE_ENDPOINT")
    if explicit:
        return explicit.rstrip("/") + "/"

    foundry = (os.environ.get("FOUNDRY_ENDPOINT") or "").rstrip("/")
    if "cognitiveservices.azure.com" in foundry:
        return foundry + "/"

    name = os.environ.get("FOUNDRY_RESOURCE_NAME")
    if name:
        return f"https://{name}.cognitiveservices.azure.com/"

    if foundry:
        print(
            "[warn] Using FOUNDRY_ENDPOINT as-is for Document Intelligence. If calls "
            "fail, set DOCUMENTINTELLIGENCE_ENDPOINT to the *.cognitiveservices.azure.com form."
        )
        return foundry + "/"

    raise RuntimeError(
        "No endpoint found. Set DOCUMENTINTELLIGENCE_ENDPOINT (or FOUNDRY_ENDPOINT / "
        "FOUNDRY_RESOURCE_NAME) in demo/classifier/.env or the repo-root .env."
    )


def get_credential():
    """AzureKeyCredential if a key is set, else DefaultAzureCredential (az login / MSI)."""
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential

    key = os.environ.get("DOCUMENTINTELLIGENCE_KEY") or os.environ.get("FOUNDRY_KEY")
    if key:
        print(" auth = AzureKeyCredential")
        return AzureKeyCredential(key)
    print(" auth = DefaultAzureCredential")
    return DefaultAzureCredential()


def get_admin_client():
    """DocumentIntelligenceAdministrationClient (build/manage classifiers)."""
    from azure.ai.documentintelligence import DocumentIntelligenceAdministrationClient

    endpoint = resolve_endpoint()
    print(f" admin client | endpoint={endpoint}")
    return DocumentIntelligenceAdministrationClient(endpoint=endpoint, credential=get_credential())


def get_di_client():
    """DocumentIntelligenceClient (run classification)."""
    from azure.ai.documentintelligence import DocumentIntelligenceClient

    endpoint = resolve_endpoint()
    print(f" analysis client | endpoint={endpoint}")
    return DocumentIntelligenceClient(endpoint=endpoint, credential=get_credential())


# --------------------------------------------------------------------------
# Storage helpers
# --------------------------------------------------------------------------
def storage_account_name(account_name: Optional[str] = None) -> str:
    name = account_name or os.environ.get("STORAGE_ACCOUNT_NAME")
    if not name:
        load_env()  # pick up a .env created after this module was imported
        name = os.environ.get("STORAGE_ACCOUNT_NAME")
    if not name:
        raise RuntimeError(
            "Set STORAGE_ACCOUNT_NAME in demo/classifier/.env (or pass account_name)."
        )
    return name


def account_url(account_name: Optional[str] = None) -> str:
    return f"https://{storage_account_name(account_name)}.blob.core.windows.net"


def container_url(account_name: Optional[str] = None, container: Optional[str] = None) -> str:
    """Plain container URL without credentials."""
    return f"{account_url(account_name)}/{container or CONTAINER}"


def get_blob_service_client(account_name: Optional[str] = None):
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    return BlobServiceClient(account_url=account_url(account_name), credential=DefaultAzureCredential())


def upload_training_data(
    blob_service=None,
    account_name: Optional[str] = None,
    container: Optional[str] = None,
) -> dict:
    """Upload each class folder to <container>/<label>/<file>. Returns per-class counts."""
    from azure.core.exceptions import ResourceExistsError

    blob_service = blob_service or get_blob_service_client(account_name)
    container = container or CONTAINER

    cc = blob_service.get_container_client(container)
    try:
        cc.create_container()
        print(f" created container '{container}'")
    except ResourceExistsError:
        print(f" container '{container}' already exists")

    counts: dict = {}
    for label, folder in CLASS_DIRS.items():
        pdfs = sorted(Path(folder).glob("*.pdf"))
        for pdf in pdfs:
            with open(pdf, "rb") as f:
                cc.upload_blob(name=f"{label}/{pdf.name}", data=f, overwrite=True)
        counts[label] = len(pdfs)
        print(f"  {label:8s} -> {len(pdfs)} file(s) under '{label}/'")
    return counts


def ensure_classifier_layout_results(
    di_client=None,
    blob_service=None,
    account_name: Optional[str] = None,
    container: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Create the raw Layout API sidecar required for each classifier document."""
    from azure.storage.blob import ContentSettings

    di_client = di_client or get_di_client()
    blob_service = blob_service or get_blob_service_client(account_name)
    container_client = blob_service.get_container_client(container or CONTAINER)
    existing = {blob.name for blob in container_client.list_blobs()}
    counts = {"created": 0, "existing": 0}

    for label, folder in CLASS_DIRS.items():
        for pdf in sorted(Path(folder).glob("*.pdf")):
            sidecar_name = f"{label}/{pdf.name}.ocr.json"
            if not force and sidecar_name in existing:
                counts["existing"] += 1
                continue

            raw_responses = []

            def capture_layout_response(response) -> None:
                try:
                    payload = response.http_response.json()
                except (AttributeError, ValueError):
                    return
                if "analyzeResult" in payload:
                    raw_responses.append(payload)

            print(f" layout: {label}/{pdf.name}")
            with open(pdf, "rb") as stream:
                poller = di_client.begin_analyze_document(
                    "prebuilt-layout",
                    body=stream,
                    raw_response_hook=capture_layout_response,
                )
                poller.result()

            if not raw_responses or raw_responses[-1].get("status") != "succeeded":
                raise RuntimeError(f"Could not capture the raw Layout response for {pdf.name}.")

            container_client.upload_blob(
                name=sidecar_name,
                data=json.dumps(raw_responses[-1], ensure_ascii=True).encode("utf-8"),
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
            )
            counts["created"] += 1

    print(
        f" layout sidecars: {counts['created']} created, "
        f"{counts['existing']} already present"
    )
    return counts


def container_sas_url(
    account_name: Optional[str] = None,
    container: Optional[str] = None,
    expiry_minutes: int = 480,
) -> str:
    """User-delegation container SAS with the rwdl permissions used for training."""
    from datetime import datetime, timedelta, timezone

    from azure.storage.blob import ContainerSasPermissions, generate_container_sas

    account = storage_account_name(account_name)
    container = container or CONTAINER
    service = get_blob_service_client(account)

    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=5)
    expiry = now + timedelta(minutes=expiry_minutes)
    delegation_key = service.get_user_delegation_key(
        key_start_time=start,
        key_expiry_time=expiry,
    )
    sas = generate_container_sas(
        account_name=account,
        container_name=container,
        user_delegation_key=delegation_key,
        permission=ContainerSasPermissions(read=True, write=True, delete=True, list=True),
        expiry=expiry,
        start=start,
    )
    return f"{container_url(account, container)}?{sas}"


def blob_sas_url(
    blob_name: str,
    account_name: Optional[str] = None,
    container: Optional[str] = None,
    expiry_minutes: int = 30,
) -> str:
    """Short-lived read-only user-delegation SAS for a single blob (no account key)."""
    from datetime import datetime, timedelta, timezone

    from azure.storage.blob import BlobSasPermissions, generate_blob_sas

    account = storage_account_name(account_name)
    container = container or CONTAINER
    svc = get_blob_service_client(account)

    start = datetime.now(timezone.utc)
    expiry = start + timedelta(minutes=expiry_minutes)
    delegation_key = svc.get_user_delegation_key(key_start_time=start, key_expiry_time=expiry)

    sas = generate_blob_sas(
        account_name=account,
        container_name=container,
        blob_name=blob_name,
        user_delegation_key=delegation_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
        start=start,
    )
    return f"{account_url(account)}/{container}/{blob_name}?{sas}"


# --------------------------------------------------------------------------
# Classifier helpers
# --------------------------------------------------------------------------
def delete_classifier_if_exists(admin_client, classifier_id: Optional[str] = None) -> bool:
    """Delete an existing classifier so a rebuild starts clean. Returns True if deleted."""
    from azure.core.exceptions import ResourceNotFoundError

    classifier_id = classifier_id or CLASSIFIER_ID
    try:
        admin_client.get_classifier(classifier_id=classifier_id)
    except ResourceNotFoundError:
        return False
    admin_client.delete_classifier(classifier_id=classifier_id)
    print(f" deleted existing classifier '{classifier_id}'")
    return True


# --------------------------------------------------------------------------
# Result formatting
# --------------------------------------------------------------------------
def summarize(result) -> list:
    """Flatten an AnalyzeResult into [{doc_type, confidence, pages}]."""
    rows = []
    for doc in (getattr(result, "documents", None) or []):
        pages = sorted({r.page_number for r in (doc.bounding_regions or [])})
        rows.append(
            {"doc_type": doc.doc_type, "confidence": doc.confidence, "pages": pages}
        )
    return rows


def print_result(result, source: str = "") -> list:
    rows = summarize(result)
    header = f"Classified {source}".strip()
    print(header)
    print("-" * max(len(header), 40))
    if not rows:
        print(" (no documents identified)")
    for r in rows:
        conf = f"{r['confidence']:.3f}" if r["confidence"] is not None else "n/a"
        print(f"  docType={r['doc_type'] or 'N/A':10s} confidence={conf}  pages={r['pages']}")
    return rows


def save_result(result, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f" cached -> {path}")
    return path
