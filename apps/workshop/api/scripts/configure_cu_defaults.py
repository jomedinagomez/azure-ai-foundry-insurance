"""One-shot setup: configure default model deployments on the workshop's
Content Understanding resource.

The SOV, SEC, and Pro analyzers use ``method: generate`` fields, which require
defaults to be set on the CU resource (otherwise CU returns
``InvalidRequest / DefaultsNotSet`` on every call). Sample runs masked this
because they're served from the cached payload under
``demo/sov/reference/cu-output/`` — file uploads always invoke the live API.

This script PATCHes ``/contentunderstanding/defaults`` with the deployment
names the rest of the workshop already uses (read from ``.env``).

Usage::

    cd apps/workshop/api
    ../../../.venv/Scripts/python.exe scripts/configure_cu_defaults.py

Requires ``az login`` on the same identity that has the
**Cognitive Services User** role on the CU resource.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


API_VERSION = "2025-11-01"

# Mirrors apps/workshop/api/standalone_api.py: load root .env first so the
# Terraform-generated values win, then layer demo/sov/.env without overriding.
_HERE = Path(__file__).resolve().parent
_API_ROOT = _HERE.parent
_REPO_ROOT = _API_ROOT.parent.parent.parent
_ROOT_ENV = _REPO_ROOT / ".env"
_API_ENV = _API_ROOT / ".env"
_SOV_ENV = _REPO_ROOT / "demo" / "sov" / ".env"

if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV)
elif _API_ENV.exists():
    load_dotenv(_API_ENV)
if _SOV_ENV.exists():
    load_dotenv(_SOV_ENV, override=False)


def _resolve_endpoint() -> str:
    endpoint = (
        os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.environ.get("CONTENTUNDERSTANDING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
    )
    if not endpoint:
        raise SystemExit(
            "Set APP_CONTENT_UNDERSTANDING_ENDPOINT (or FOUNDRY_ENDPOINT) "
            "in .env before running this script."
        )
    return endpoint.rstrip("/")


def _resolve_deployments() -> dict[str, str]:
    """Map CU model identifiers to deployment names from the workshop .env.

    Falls back to convention-named deployments when the env doesn't override.
    """
    return {
        "gpt-4.1": os.environ.get("GPT41_MODEL_DEPLOYMENT", "gpt-4.1"),
        "gpt-4.1-mini": (
            os.environ.get("GPT41_MINI_MODEL_DEPLOYMENT")
            or os.environ.get("APP_CU_COMPLETION_DEPLOYMENT")
            or "gpt-4.1-mini"
        ),
        "text-embedding-3-large": os.environ.get(
            "EMBEDDING_MODEL_DEPLOYMENT", "text-embedding-3-large"
        ),
    }


def main() -> int:
    endpoint = _resolve_endpoint()
    deployments = _resolve_deployments()
    url = f"{endpoint}/contentunderstanding/defaults?api-version={API_VERSION}"

    print(f"Endpoint:    {endpoint}")
    print("Deployments:")
    for model, dep in deployments.items():
        print(f"  {model:<25} -> {dep}")
    print(f"PATCH        {url}\n")

    token = DefaultAzureCredential().get_token(
        "https://cognitiveservices.azure.com/.default"
    )
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/merge-patch+json",
    }
    body = {"modelDeployments": deployments}

    resp = requests.patch(url, headers=headers, data=json.dumps(body), timeout=30)

    if not resp.ok:
        print(f"FAILED  HTTP {resp.status_code} {resp.reason}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        if resp.status_code in (401, 403):
            print(
                "\nHint: the signed-in identity needs the 'Cognitive Services User' "
                "role on the CU resource. Sign in with `az login` as a user that has it.",
                file=sys.stderr,
            )
        return 1

    result = resp.json() if resp.text else {}
    print("OK — defaults updated.")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
