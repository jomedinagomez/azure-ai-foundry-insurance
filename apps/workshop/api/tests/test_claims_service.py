import hashlib
import json
import uuid
from contextlib import nullcontext

from app.services import claims_service as service


def test_all_six_folders_and_nested_email_are_read_locally(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAIMS_OUTPUT_ROOT", str(tmp_path))
    overview = service.list_claims()

    assert len(overview["claims"]) == 6
    assert sum(claim["original_files"] for claim in overview["claims"]) == 62
    assert all(claim["chunks"] == 0 for claim in overview["claims"])
    items, skipped, _ = service.inventory("claim-003")
    nested = [item for item in items.values() if item.source_type == "email" and item.parent_emails]
    assert nested
    assert any("::" in source for item in nested for source in item.source_files)
    assert any("signature" in item["source"] for item in skipped)


def test_schema_matches_the_page_free_notebook_contract():
    index = service._index()
    assert [field.name for field in index.fields] == service.COLUMNS
    assert "page_num" not in service.COLUMNS
    assert "title_vector" not in service.COLUMNS
    assert index.fields[-1].hidden
    assert index.semantic_search.default_configuration_name == "claims-semantic"


def _sample_evidence(tmp_path):
    pdf = service.Evidence("a" * 64, "report.pdf", "document", str(tmp_path / "report.pdf"),
                           data=b"%PDF", source_files=["claim-001/report.pdf"])
    image = service.Evidence("b" * 64, "photo.png", "image", str(tmp_path / "photo.png"),
                             data=b"image", source_files=["claim-001/photo.png"])
    email = service.Evidence("c" * 64, "notification.msg", "email", str(tmp_path / "notification.msg"),
                             text="# Notification\n\nPlease inspect the roof.",
                             source_files=["claim-001/notification.msg"])
    image.parent_emails = [email.document_hash]
    items = {item.document_hash: item for item in [pdf, image, email]}
    results = {
        pdf.document_hash: {
            "analyzerId": "prebuilt-documentSearch", "apiVersion": "2025-11-01",
            "contents": [{"markdown": "# Inspection\n\n## Observations\n\nBent panels.",
                          "figures": [{"id": "1.1", "source": "D(1,0,0,1,1)", "description": "A roof diagram."}]}],
        },
        image.document_hash: {
            "analyzerId": "prebuilt-imageSearch", "apiVersion": "2025-11-01",
            "contents": [{"markdown": "![image](pages/1)", "fields": {"Summary": {"valueString": "Bent panels; timing cannot be determined."}}}],
        },
    }
    return items, results


def test_chunks_preserve_native_observations_and_email_parentage(tmp_path):
    items, results = _sample_evidence(tmp_path)
    routes = {key: service._route(item, set()) for key, item in items.items()}
    rows = service._chunk_rows("claim-001", items, results, routes)
    image = next(row for row in rows if row["source_type"] == "image")

    assert image["content"] == "Bent panels; timing cannot be determined."
    assert image["parent_emails"] == ["c" * 64]
    assert image["id"] == hashlib.sha256(f"claim-001:{'b' * 64}:1".encode()).hexdigest()
    assert {row["content_kind"] for row in rows} == {
        "document_text", "figure_description", "image_description", "email_text",
    }
    assert all("page_num" not in row for row in rows)
    assert len({row["id"] for row in rows}) == len(rows)
    assert service._route(items["b" * 64], {"photo.png"}) == "prebuilt-documentSearch"


def test_repeated_progress_writes_in_the_configured_output_directory():
    path = service.output_root() / f".claims-write-verification-{uuid.uuid4().hex}.json"
    try:
        for sequence in range(20):
            service._write(path, {"sequence": sequence})
            assert service._read(path) == {"sequence": sequence}
    finally:
        if path.exists():
            path.unlink()


def test_cached_processing_reuses_vectors_without_any_azure_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAIMS_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_CONTENT_UNDERSTANDING_ENDPOINT", "https://example.services.ai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "3")
    monkeypatch.setenv("CU_API_VERSION", "2025-11-01")
    items, results = _sample_evidence(tmp_path)
    routes = {key: service._route(item, set()) for key, item in items.items()}
    rows = service._chunk_rows("claim-001", items, results, routes)
    for row in rows:
        row["content_vector"] = [0.1, 0.2, 0.3]
    service._write(tmp_path / "claim-001" / "processed-evidence-v1.json", rows)
    for key, result in results.items():
        service._write(service._cache_path(items[key], routes[key]), result)

    class NoCloudCalls:
        def __getattr__(self, name):
            raise AssertionError(f"Unexpected Azure call: {name}")

    monkeypatch.setattr(service, "inventory", lambda _claim: (items, [], 3))
    monkeypatch.setattr(service, "DefaultAzureCredential", lambda: nullcontext(NoCloudCalls()))
    monkeypatch.setattr(service, "ContentUnderstandingClient", lambda **_kwargs: nullcontext(NoCloudCalls()))
    monkeypatch.setattr(service, "OpenAI", lambda **_kwargs: nullcontext(NoCloudCalls()))
    monkeypatch.setattr(service, "get_bearer_token_provider", lambda *_args: "unused")
    monkeypatch.setattr(service, "_job", {"events": [], "status": "running"})

    service._process("claim-001", False, set())

    saved = service._read(tmp_path / "claim-001" / "processed-evidence-v1.json")
    assert saved == [{name: row[name] for name in service.COLUMNS} for row in rows]
    assert service._job["stage"] == "embed"
    assert "content_vector" not in service._public_chunk(saved[0])
    assert service._public_chunk(saved[0])["vector_dimensions"] == 3


def test_image_file_detail_prefers_native_summary_over_image_markdown(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAIMS_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setenv("CU_API_VERSION", "2025-11-01")
    items, results = _sample_evidence(tmp_path)
    image = items["b" * 64]
    monkeypatch.setattr(service, "inventory", lambda _claim: ({image.document_hash: image}, [], 1))
    service._write(service._cache_path(image, "prebuilt-imageSearch"), results[image.document_hash])

    detail = service.file_detail("claim-001", image.document_hash)
    assert detail["native_text"] == "Bent panels; timing cannot be determined."


def test_notebook_cache_chunk_parity_when_saved_outputs_exist():
    items, _, _ = service.inventory("claim-001")
    records = service._records("claim-001")
    if not records:
        import pytest
        pytest.skip("Run notebook 1 locally to check parity with its complete saved records.")
    routes = {row["document_hash"]: row["analyzer_id"] for row in records}
    results = {}
    for key, item in items.items():
        if item.source_type != "email":
            path = service._cache_path(item, routes[key])
            if not path.exists():
                import pytest
                pytest.skip("Native CU cache is not present for every prepared document.")
            results[key] = json.loads(path.read_text(encoding="utf-8"))
    rows = service._chunk_rows("claim-001", items, results, routes)
    assert len(rows) == len(records)
    previous = {row["id"]: row for row in records}
    assert all(service._embedding_text(row) == service._embedding_text(previous[row["id"]]) for row in rows)
