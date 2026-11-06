"""Foundry external-agent identity and real Azure Monitor telemetry."""
import os
import re
import threading
from urllib.parse import urlparse

import httpx
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ExternalAgentDefinition
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource

_lock = threading.Lock()
_credential: DefaultAzureCredential | None = None
_application_id: str | None = None
_configured_project: str | None = None


def project_endpoint() -> str:
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").rstrip("/")
    if not endpoint:
        raise ValueError("Configure AZURE_AI_PROJECT_ENDPOINT in the root .env.")
    return endpoint


def project_portal_url() -> str:
    project = urlparse(project_endpoint())
    account = project.hostname.split(".")[0] if project.hostname else ""
    name = project.path.rsplit("/", 1)[-1]
    return (f"https://portal.azure.com/#resource/subscriptions/{os.getenv('AZURE_SUBSCRIPTION_ID', '')}"
            f"/resourceGroups/{os.getenv('AZURE_RESOURCE_GROUP', '')}"
            f"/providers/Microsoft.CognitiveServices/accounts/{account}/projects/{name}/overview")


def discover_telemetry(credential: DefaultAzureCredential) -> tuple[str, str]:
    project = urlparse(project_endpoint())
    account = project.hostname.split(".")[0] if project.hostname else ""
    name = project.path.rsplit("/", 1)[-1]
    subscription = os.environ["AZURE_SUBSCRIPTION_ID"]
    group = os.environ["AZURE_RESOURCE_GROUP"]
    token = credential.get_token("https://management.azure.com/.default").token
    headers = {"Authorization": f"Bearer {token}"}
    account_id = f"/subscriptions/{subscription}/resourceGroups/{group}/providers/Microsoft.CognitiveServices/accounts/{account}"
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.get(
            f"https://management.azure.com{account_id}/projects/{name}/connections",
            params={"api-version": "2025-06-01"}, headers=headers)
        response.raise_for_status()
        connections = [item["properties"] for item in response.json()["value"]
                       if item["properties"].get("category") == "AppInsights"]
        if len(connections) != 1:
            raise ValueError("The selected Foundry project must have exactly one Application Insights connection.")
        resource_id = connections[0]["target"]
        if not re.fullmatch(r"/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft.Insights/components/[^/]+", resource_id, re.I):
            raise ValueError("The project's Application Insights target is not an ARM component resource.")
        response = client.get(f"https://management.azure.com{resource_id}",
                              params={"api-version": "2020-02-02"}, headers=headers)
        response.raise_for_status()
        properties = response.json()["properties"]
        return properties["ConnectionString"], properties["AppId"]


def register_external_agent(name: str, recipe: str) -> dict:
    with DefaultAzureCredential() as credential:
        # Resolve the selected project's telemetry destination, not a second monitoring resource.
        discover_telemetry(credential)
        with AIProjectClient(endpoint=project_endpoint(), credential=credential, allow_preview=True) as client:
            version = client.agents.create_version(
                agent_name=name, definition=ExternalAgentDefinition(otel_agent_id=name),
                description="Read-only claims assistant running locally in Insurance Workbench; registration is telemetry metadata, not hosted compute.",
                metadata={"runtime": "local", "recipe": recipe, "tools": "semantic_search,structured_claim_api"},
            )
    return {"name": version.name, "version": version.version, "id": version.id,
            "otel_agent_id": version.definition.otel_agent_id}


def ensure_telemetry() -> None:
    global _credential, _application_id, _configured_project
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
    with _lock:
        endpoint = project_endpoint()
        if _configured_project:
            if _configured_project != endpoint:
                raise ValueError("Restart the API before changing the Foundry tracing destination.")
            return
        credential = DefaultAzureCredential()
        try:
            connection_string, app_id = discover_telemetry(credential)
            os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"
            configure_azure_monitor(
                connection_string=connection_string, credential=credential,
                resource=Resource.create({"service.name": "insurance-workbench-claims-agent"}),
                enable_live_metrics=False, sampling_ratio=1.0,
            )
            instrumentor = OpenAIInstrumentor()
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
        except Exception:
            credential.close()
            raise
        _credential, _application_id, _configured_project = credential, app_id, endpoint


def attributes(binding: dict, conversation_id: str) -> dict:
    return {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.id": binding["otel_agent_id"],
        "gen_ai.agent.name": binding["name"],
        "gen_ai.agent.version": binding["version"],
        "gen_ai.conversation.id": conversation_id,
        "conversation.id": conversation_id,
        "gen_ai.request.model": binding["model"],
        "claims.runtime": "local",
    }


def flush() -> str:
    provider = trace.get_tracer_provider()
    if not hasattr(provider, "force_flush") or not provider.force_flush(timeout_millis=10000):
        return "Telemetry flush did not complete; cloud ingestion is unverified."
    return "Telemetry flushed to the exporter; cloud ingestion is not yet verified."


def cloud_evidence(trace_id: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", trace_id):
        raise ValueError("Invalid trace ID.")
    query = (
        "union requests, dependencies\n"
        "| where timestamp > ago(24h)\n"
        f"| where operation_Id == '{trace_id}'\n"
        "| project timestamp, name, operation_Id, id, operation_ParentId, customDimensions\n"
        "| take 50"
    )
    with DefaultAzureCredential() as credential:
        _, application_id = discover_telemetry(credential)
        token = credential.get_token("https://api.applicationinsights.io/.default").token
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.get(
                f"https://api.applicationinsights.io/v1/apps/{application_id}/query",
                params={"query": query, "timespan": "P1D"},
                headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
    tables = response.json().get("tables", [])
    rows = []
    for table in tables:
        columns = [column["name"] for column in table["columns"]]
        rows.extend(dict(zip(columns, row)) for row in table["rows"])
    return {"trace_id": trace_id, "verified": bool(rows), "span_count": len(rows),
            "query": query, "spans": rows,
            "message": "Matching spans observed in the project's Application Insights." if rows
            else "No matching spans observed yet. Export and ingestion can lag; this is not proof of failure."}
