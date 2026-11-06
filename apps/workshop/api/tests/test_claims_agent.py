import json
from contextlib import nullcontext
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

import standalone_api
from app.services import claim_operations_service as operations
from app.services import claims_agent_service as service
from app.services import claims_agent_telemetry as telemetry


@pytest.fixture
def local(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAIMS_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/claims")
    monkeypatch.setenv("APP_CU_COMPLETION_DEPLOYMENT", "gpt-5.2")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "3072")
    monkeypatch.setenv("CLAIMS_AGENT_NAME", "claims-local-assistant")
    monkeypatch.setattr(telemetry, "register_external_agent", lambda name, recipe: {
        "name": name, "version": "1", "id": f"{name}:1", "otel_agent_id": name,
    })
    monkeypatch.setattr(telemetry, "ensure_telemetry", lambda: None)
    monkeypatch.setattr(telemetry, "flush", lambda: "Test exporter only; cloud ingestion unverified.")
    monkeypatch.setattr(service, "DefaultAzureCredential", lambda: nullcontext(object()))
    monkeypatch.setattr(service, "OpenAI", lambda **kwargs: nullcontext(object()))
    monkeypatch.setattr(service, "get_bearer_token_provider", lambda *_args: "test-token-provider")
    return TestClient(standalone_api.app)


def register_and_create(client):
    assert client.post("/claims-agent/register").status_code == 200
    response = client.post("/claims-agent/conversations", json={"claim_id": "claim-001"})
    assert response.status_code == 201
    return response.json()["id"]


def model_reply(*calls, answer=None):
    message = SimpleNamespace(
        refusal=None, content=answer, tool_calls=list(calls),
        model_dump=lambda **_kwargs: {"role": "assistant", "tool_calls": [
            {"id": call.id, "type": "function", "function": {
                "name": call.function.name, "arguments": call.function.arguments,
            }} for call in calls]},
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="tool_calls" if calls else "stop")],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10),
    )


def tool_call(name, args, id="call-1"):
    return SimpleNamespace(id=id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def test_status_is_local_and_chat_never_registers_implicitly(local, monkeypatch):
    calls = []
    monkeypatch.setattr(telemetry, "register_external_agent", lambda *_args: calls.append("register"))
    assert local.get("/claims-agent/status").json()["registered"] is False
    assert local.get("/claims-agent/conversations?claim_id=claim-001").json() == []
    assert local.post("/claims-agent/conversations", json={"claim_id": "claim-001"}).status_code == 422
    assert calls == []


def test_selected_claim_is_bound_server_side_and_arguments_cannot_override_it(local):
    with pytest.raises(ValueError):
        service._tools("get_structured_claim", '{"claim_id":"claim-002"}', "claim-001", [])
    with pytest.raises(ValueError):
        service._tools("search_claim_evidence", '{"question":"roof","claim_id":"claim-002"}', "claim-001", [])
    with pytest.raises(ValueError, match="allowlist"):
        service._tools("pay_claim", "{}", "claim-001", [])


def test_two_tools_produce_a_grounded_answer_with_persisted_actual_steps(local, monkeypatch):
    conversation = register_and_create(local)
    calls = iter([
        model_reply(tool_call("search_claim_evidence", {"question": "What is outstanding?"})),
        model_reply(tool_call("get_structured_claim", {}, "call-2")),
        model_reply(answer="The file still needs corroboration [D1]. The reserve is USD 25,000.00 and paid expense is USD 375.00 in the synthetic snapshot [S1]."),
    ])
    monkeypatch.setattr(service, "_call_model", lambda *_args: next(calls))
    monkeypatch.setattr(service.evidence, "search", lambda claim, question: [{
        "id": "evidence-1", "claim_id": claim, "title": "Inspection", "header": "Outstanding",
        "content": "Incident-time corroboration is outstanding.", "filename": "inspection.pdf",
        "content_kind": "document_text", "chunk_id": 1, "source_files": ["claim-001/inspection.pdf"],
        "parent_emails": [], "semantic_score": 2.5, "document_hash": "document-hash",
    }])
    requested = []
    def get_snapshot(_client, url):
        requested.append(url)
        return httpx.Response(200, json=operations.get_snapshot("claim-001").model_dump(mode="json"),
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", get_snapshot)
    response = local.post(f"/claims-agent/conversations/{conversation}/messages", json={"question": "What is outstanding and how much is reserved?"})
    turn = response.json()["turns"][0]
    assert turn["status"] == "complete"
    assert requested == ["http://127.0.0.1:8000/claims-operations/claims/claim-001"]
    assert [step["name"] for step in turn["steps"] if step["kind"] == "tool"] == ["search_claim_evidence", "get_structured_claim"]
    assert {citation["id"] for citation in turn["citations"]} == {"D1", "S1"}
    assert turn["steps"][3]["result"]["data"]["financials"]["paid_total"] == "375.00"
    assert local.request("GET", f"/claims-agent/conversations/{conversation}").json()["turns"][0] == turn
    assert len(local.request("GET", "/claims-agent/conversations?claim_id=claim-001").json()) == 1
    assert local.request("GET", "/claims-agent/conversations?claim_id=claim-002").json() == []


def test_provider_or_tool_failure_is_recorded_not_an_assistant_answer(local, monkeypatch):
    conversation = register_and_create(local)
    monkeypatch.setattr(service, "_call_model", lambda *_args: model_reply(tool_call("get_structured_claim", {})))
    def denied(*_args):
        raise RuntimeError("Structured tool unavailable")
    monkeypatch.setattr(service, "_tools", denied)
    turn = local.post(f"/claims-agent/conversations/{conversation}/messages", json={"question": "What has been paid?"}).json()["turns"][0]
    assert turn["status"] == "failed"
    assert turn["answer"] is None
    assert turn["steps"][-1]["error"] == "Structured tool unavailable"
    assert turn["steps"][-1]["status"] == "failed"


def test_agent_call_budget_stops_tool_loops(local, monkeypatch):
    conversation = register_and_create(local)
    monkeypatch.setattr(service, "_call_model", lambda *_args: model_reply(tool_call("get_structured_claim", {})))
    monkeypatch.setattr(service, "_tools", lambda *_args: {"observed": True})
    turn = local.post(f"/claims-agent/conversations/{conversation}/messages", json={"question": "Keep checking"}).json()["turns"][0]
    assert turn["status"] == "failed"
    assert "six-tool-call limit" in turn["error"]
    assert len([step for step in turn["steps"] if step["kind"] == "tool"]) == 6


def test_unknown_citations_and_version_mismatches_are_not_accepted(local, monkeypatch):
    conversation = register_and_create(local)
    monkeypatch.setattr(service, "_call_model", lambda *_args: model_reply(answer="Everything is approved [D99]."))
    turn = local.post(f"/claims-agent/conversations/{conversation}/messages", json={"question": "Is it approved?"}).json()["turns"][0]
    assert turn["status"] == "failed"
    assert "identifiers" in turn["error"]
    monkeypatch.setenv("CLAIMS_AGENT_MODEL_DEPLOYMENT", "different-model")
    assert local.get("/claims-agent/status").json()["registered"] is False
    assert local.post(f"/claims-agent/conversations/{conversation}/messages", json={"question": "Again"}).status_code == 422


def test_structured_tool_refuses_wrong_claim_payload(local, monkeypatch):
    def wrong(_client, url):
        return httpx.Response(200, json=operations.get_snapshot("claim-002").model_dump(mode="json"),
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", wrong)
    with pytest.raises(ValueError, match="different claim"):
        service._tools("get_structured_claim", "{}", "claim-001", [])


def test_http_tool_is_loopback_only(local, monkeypatch):
    monkeypatch.setenv("CLAIMS_STRUCTURED_API_BASE_URL", "https://outside.example.com")
    with pytest.raises(ValueError, match="loopback"):
        service._api_base()


def test_telemetry_failure_does_not_fall_back_to_untraced_model_calls(local, monkeypatch):
    conversation = register_and_create(local)
    def failed():
        raise RuntimeError("Telemetry destination unavailable")
    monkeypatch.setattr(telemetry, "ensure_telemetry", failed)
    monkeypatch.setattr(service, "_call_model", lambda *_args: pytest.fail("No untraced model fallback allowed"))
    turn = local.post(f"/claims-agent/conversations/{conversation}/messages", json={"question": "What is paid?"}).json()["turns"][0]
    assert turn["status"] == "failed"
    assert turn["trace_id"] is None
    assert turn["answer"] is None


def test_invalid_conversation_ids_do_not_access_paths(local):
    assert local.get("/claims-agent/conversations/not-a-real-id").status_code == 404
    assert local.post("/claims-agent/conversations", json={"claim_id": "claim-999"}).status_code == 404


def test_prior_evidence_is_not_promoted_to_a_system_instruction(local, monkeypatch):
    conversation = register_and_create(local)
    saved = service.get_conversation(conversation)
    saved["turns"].append({"id": "previous", "status": "complete", "question": "First question",
                           "answer": "Prior source [D1].", "citations": [
                               {"id": "D1", "kind": "document", "excerpt": "Untrusted source text"}]})
    service._save(saved)
    seen = []
    def reply(_client, messages, _model):
        seen.extend(messages)
        return model_reply(answer="The prior source remains unverified [D1].")
    monkeypatch.setattr(service, "_call_model", reply)
    result = service.send_message(conversation, "What about that source?")
    assert result["turns"][-1]["status"] == "complete"
    assert [message["role"] for message in seen] == ["system", "user", "assistant", "user"]
    assert "Untrusted source text" not in seen[0]["content"]


def test_cloud_verification_rejects_another_project_binding(local):
    conversation = register_and_create(local)
    saved = service.get_conversation(conversation)
    saved["project_endpoint"] = "https://other.example/api/projects/other"
    service._save(saved)
    with pytest.raises(ValueError, match="another Foundry project"):
        service.check_trace(conversation, "unknown")
