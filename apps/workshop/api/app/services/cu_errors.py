"""Helpers for turning raw Content Understanding SDK / REST errors into
short, actionable messages we can return from the API and surface in the UI.

Today this only covers the two errors users hit most often when running an
analyzer that wasn't preconfigured on their CU resource:

* ``DefaultsNotSet`` — the CU resource has no default model deployments,
  so any analyzer that uses ``generate`` fields fails immediately.
* ``ContentEmpty`` — CU couldn't extract any content from the upload
  (corrupt PDF, password-protected, etc.).

The matching is best-effort — we look for the error code anywhere in the
exception's string form (Azure SDK ``HttpResponseError`` formats its body
in there), and also try ``response.text()`` when available.
"""

from __future__ import annotations

import json
from typing import Optional


_FRIENDLY_BY_CODE = {
    "DefaultsNotSet": (
        "This Content Understanding resource is missing default model "
        "deployments, which are required for SOV / SEC / Pro analyzers that "
        "use `generate` fields. Have an admin run "
        "`PATCH /contentunderstanding/defaults` on the CU resource (or "
        "configure defaults from the Foundry portal). See "
        "https://learn.microsoft.com/azure/ai-services/content-understanding/quickstart for the one-time setup."
    ),
    "ContentEmpty": (
        "Content Understanding could not extract any content from the "
        "uploaded file. Check that it is a supported format and is not "
        "empty, corrupt, or password-protected."
    ),
}


def _extract_error_payload(exc: BaseException) -> dict:
    """Best-effort: return the inner ``{'error': {...}}`` dict from an exception."""
    # 1) azure-core HttpResponseError exposes the raw response body
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            text = resp.text() if callable(getattr(resp, "text", None)) else getattr(resp, "text", "")
            if text:
                return json.loads(text)
        except Exception:
            pass
    # 2) Fall back to scanning the str() form
    s = str(exc)
    if "{" in s:
        try:
            start = s.index("{")
            return json.loads(s[start:])
        except Exception:
            pass
    return {}


def friendly_cu_error(exc: BaseException) -> Optional[str]:
    """Return a human-readable explanation if *exc* matches a known CU error.

    Returns ``None`` when the exception doesn't look like one of the cases
    we have a friendly message for — callers should then fall back to their
    existing generic error path.
    """
    body = _extract_error_payload(exc)
    err = (body or {}).get("error", {}) if isinstance(body, dict) else {}
    inner = err.get("innererror", {}) if isinstance(err, dict) else {}
    inner_code = inner.get("code") if isinstance(inner, dict) else None

    if inner_code and inner_code in _FRIENDLY_BY_CODE:
        return _FRIENDLY_BY_CODE[inner_code]

    # Last-ditch: substring match on the stringified exception for cases
    # where the SDK didn't surface a structured body.
    s = str(exc)
    for code, message in _FRIENDLY_BY_CODE.items():
        if code in s:
            return message
    return None


def cu_error_status_code(exc: BaseException) -> int:
    """HTTP status to surface for a CU error.

    ``DefaultsNotSet`` is a configuration problem on the resource, not a bad
    request — surface as 503 so the UI can render it as an environment issue
    rather than a validation error.
    """
    body = _extract_error_payload(exc)
    inner = (((body or {}).get("error", {}) or {}).get("innererror", {}) or {})
    code = inner.get("code") or ""
    if not code and "DefaultsNotSet" in str(exc):
        code = "DefaultsNotSet"
    if code == "DefaultsNotSet":
        return 503
    if code == "ContentEmpty":
        return 422
    return 422
