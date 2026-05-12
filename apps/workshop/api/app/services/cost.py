"""Cost estimation for SOV pipelines and Analyzer Compare runs.

The numbers here are **estimates**, not invoices. Real Azure billing reflects
contracted rates, regional differences, and platform-level discounts we
don't model. The intent is to give end-users an at-a-glance "what order of
magnitude did this run cost" — useful for ROI conversations and catching
runaway pipelines, not for invoicing.

Pricing lives in `pricing.json` next to this module so it can be tuned
without code changes. Override any line item with your contracted rate.

Estimates are driven entirely by Content Understanding's `usage` block,
which it returns alongside each analyze response:

    {
      "documentPagesMinimal":  N,    // per-tier page counts; CU picks the
      "documentPagesBasic":    N,    // tier based on what processing it
      "documentPagesStandard": N,    // actually performed
      "audioHours":   ...,
      "videoHours":   ...,
      "contextualizationTokens": N,  // billed per docs (1$/1M tokens)
      "tokens": { "<model>-input": N, "<model>-output": N, ... }
    }

Per the public pricing docs:
    Total = Content Extraction + Contextualization + LLM Input + LLM Output
            (+ Embeddings, if labeled training data is used)

There's nothing in our code that picks a tier or decides what to bill —
CU's response is the source of truth. We just multiply each counter by
its configured rate.

Sources:
- https://azure.microsoft.com/pricing/details/content-understanding/
- https://learn.microsoft.com/azure/ai-services/content-understanding/pricing-explainer

Public API:

- `estimate_cu_cost(payload)`               -> CostBreakdown
- `estimate_di_cost(payload, analyzer_id)`  -> CostBreakdown
- `estimate_pipeline_cost(payload, *, include_compute=True)` -> CostBreakdown
- `sum_breakdowns(iterable)`                -> CostBreakdown
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

_PRICING_PATH = Path(__file__).with_name("pricing.json")


@lru_cache(maxsize=1)
def _pricing() -> dict[str, Any]:
    """Load (and cache) the pricing JSON. Call `reload_pricing()` to refresh."""
    with _PRICING_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def reload_pricing() -> None:
    """Drop the cached pricing dict; next call to `_pricing()` re-reads disk."""
    _pricing.cache_clear()


# ── Helpers ────────────────────────────────────────────────────────────────


def _round(v: float, places: int = 4) -> float:
    return round(v, places)


def _empty_breakdown() -> dict[str, Any]:
    return {
        "currency": _pricing().get("currency", "USD"),
        "total": 0.0,
        "components": [],
        "inputs": {},
    }


def _add_component(
    bd: dict[str, Any], label: str, qty: float, unit: str, amount: float
) -> None:
    bd["components"].append(
        {"label": label, "qty": qty, "unit": unit, "amount": _round(amount)}
    )
    bd["total"] = _round(bd["total"] + amount)


def _count_pages(payload: dict[str, Any]) -> int:
    """Sum `pages[]` lengths across every content in a CU/DI payload."""
    contents = payload.get("contents") or []
    n = 0
    for c in contents:
        n += len(c.get("pages") or [])
    return max(n, 1)  # never under-bill: a 0-page result is implausible


_LLMSTATS_RE = re.compile(r"completion calls?:\s*(\d+)", re.I)


def _count_completion_calls(payload: dict[str, Any]) -> int:
    """Parse the CU 'LLMStats' warning for completion-call count.

    Format observed: `"completion calls: 3; completion latency: 12.38s"`.
    Returns 0 when no LLM-backed fields are present (e.g. layout-only).
    """
    total = 0
    for w in payload.get("warnings") or []:
        if (w or {}).get("code") != "LLMStats":
            continue
        m = _LLMSTATS_RE.search(str(w.get("message", "")))
        if m:
            total += int(m.group(1))
    return total


def _real_usage(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return CU's `usage` block when present.

    The 2025-11-01 GA response includes a top-level `usage` object with:
      - `documentPagesMinimal|Basic|Standard`: per-tier page counts
      - `audioHours` / `videoHours`
      - `contextualizationTokens` (also seen as `contextualizationToken`
        in some doc snippets — we read both)
      - `tokens`: dict keyed by `<model>-input` / `<model>-output`
    """
    u = payload.get("usage")
    if isinstance(u, dict):
        return u
    return None


def _context_tokens(usage: dict[str, Any] | None) -> int:
    """Read contextualization-token count tolerating both spellings the
    docs use (`contextualizationTokens` vs `contextualizationToken`)."""
    if not usage:
        return 0
    raw = usage.get("contextualizationTokens", usage.get("contextualizationToken", 0))
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _tokens_by_model(usage: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Reshape `usage.tokens` from flat `<model>-input` / `<model>-output`
    keys into `{model_name: {"input": n, "output": n}}`."""
    out: dict[str, dict[str, int]] = {}
    tokens = (usage or {}).get("tokens") or {}
    for k, v in tokens.items():
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if k.endswith("-input"):
            model = k[: -len("-input")]
            out.setdefault(model, {"input": 0, "output": 0})["input"] += n
        elif k.endswith("-output"):
            model = k[: -len("-output")]
            out.setdefault(model, {"input": 0, "output": 0})["output"] += n
    return out


# ── CU (Content Understanding) cost ────────────────────────────────────────


def estimate_cu_cost(payload: dict[str, Any]) -> dict[str, Any]:
    """Estimate cost of a CU analyze call from the response's `usage` block.

    Follows the public pricing model:
        Total = Content Extraction + Contextualization + LLM tokens

    - **Content extraction** is billed per 1,000 pages at the tier CU
      reports (minimal / basic / standard), or per hour for audio/video.
    - **Contextualization tokens** accrue whenever generative features run
      (field extraction, figure analysis, segmentation, categorization,
      training). Billed at `pricing.cu.contextualization_per_1m_tokens`.
    - **LLM tokens** come from the Foundry model deployment CU calls under
      the hood. Whenever `usage.tokens` is non-empty, we bill the input
      and output token counts at the configured per-model rate.

    Nothing here picks tiers or decides whether to bill tokens — CU's
    response is the source of truth.
    """
    p = _pricing()
    bd = _empty_breakdown()
    cu = p.get("cu", {}) or {}

    usage = _real_usage(payload)

    # ── Content extraction: pages (by tier) + audio/video hours ────────────
    tiers = ("minimal", "basic", "standard")
    pages_by_tier = {t: 0 for t in tiers}
    if usage:
        pages_by_tier["minimal"] = int(usage.get("documentPagesMinimal") or 0)
        pages_by_tier["basic"] = int(usage.get("documentPagesBasic") or 0)
        pages_by_tier["standard"] = int(usage.get("documentPagesStandard") or 0)

    audio_hours = float((usage or {}).get("audioHours") or 0.0) if usage else 0.0
    video_hours = float((usage or {}).get("videoHours") or 0.0) if usage else 0.0

    per_1000 = cu.get("per_1000_pages", {}) or {}
    for tier in tiers:
        n = pages_by_tier[tier]
        if not n:
            continue
        rate_per_1000 = float(per_1000.get(tier, 0.0))
        amount = (n / 1000.0) * rate_per_1000
        _add_component(
            bd,
            f"CU content extraction — {tier} ({n} pages @ ${rate_per_1000:.2f}/1k)",
            qty=n,
            unit="page",
            amount=amount,
        )

    if audio_hours > 0:
        rate = float(cu.get("per_audio_hour", 0.0))
        _add_component(
            bd,
            f"CU audio ({audio_hours:.2f}h @ ${rate:.2f}/h)",
            qty=audio_hours,
            unit="hour",
            amount=audio_hours * rate,
        )
    if video_hours > 0:
        rate = float(cu.get("per_video_hour", 0.0))
        _add_component(
            bd,
            f"CU video ({video_hours:.2f}h @ ${rate:.2f}/h)",
            qty=video_hours,
            unit="hour",
            amount=video_hours * rate,
        )

    # ── Contextualization tokens (charged whenever generative features run)
    context_tokens = _context_tokens(usage)
    if context_tokens > 0:
        ctx_per_1m = float(cu.get("contextualization_per_1m_tokens", 0.0))
        amount = (context_tokens / 1_000_000.0) * ctx_per_1m
        _add_component(
            bd,
            f"CU contextualization ({context_tokens:,} tokens @ ${ctx_per_1m:.2f}/1M)",
            qty=context_tokens,
            unit="token",
            amount=amount,
        )

    # ── LLM tokens (per Foundry model deployment) ──────────────────────────
    real_models: dict[str, dict[str, int]] = (
        _tokens_by_model(usage) if usage else {}
    )
    real_input = sum(m["input"] for m in real_models.values())
    real_output = sum(m["output"] for m in real_models.values())

    oai = p.get("openai", {}) or {}
    model_prices = (oai.get("models") or {})
    default_model = str(oai.get("default_model", "gpt-4.1"))

    def _price_for(model: str) -> tuple[float, float]:
        m = model_prices.get(model) or model_prices.get(default_model) or {}
        return float(m.get("input_per_1k", 0.0)), float(m.get("output_per_1k", 0.0))

    for model, counts in real_models.items():
        if counts["input"] == 0 and counts["output"] == 0:
            continue
        in_per_1k, out_per_1k = _price_for(model)
        amount = (counts["input"] / 1000.0) * in_per_1k + (
            counts["output"] / 1000.0
        ) * out_per_1k
        _add_component(
            bd,
            f"{model} ({counts['input']:,} in @ ${in_per_1k * 1000:.2f}/1M, "
            f"{counts['output']:,} out @ ${out_per_1k * 1000:.2f}/1M)",
            qty=counts["input"] + counts["output"],
            unit="token",
            amount=amount,
        )

    bd["inputs"] = {
        "pages_by_tier": pages_by_tier,
        "pages_from_payload": _count_pages(payload),
        "audio_hours": audio_hours,
        "video_hours": video_hours,
        "completion_calls": _count_completion_calls(payload),
        "contextualization_tokens": context_tokens,
        "llm_input_tokens": real_input,
        "llm_output_tokens": real_output,
        "llm_models": list(real_models.keys()),
        "used_real_usage": bool(usage),
    }
    return bd


# ── DI (Document Intelligence) cost ────────────────────────────────────────


def _count_pages_di(payload: dict[str, Any]) -> int:
    """Count pages from a DI analyze response.

    DI wraps results under `analyzeResult` with `pages[]` at that level —
    different from CU's `contents[].pages[]`. We try DI's shape first and
    fall back to CU-style. Never returns less than 1 (a 0-page DI
    response is implausible and would under-bill)."""
    ar = payload.get("analyzeResult") or {}
    pages = ar.get("pages") or []
    if pages:
        return len(pages)
    # CU-shaped fallback (some prebuilts emit this when called via CU APIs)
    return _count_pages(payload)


def estimate_di_cost(payload: dict[str, Any], *, analyzer_id: str) -> dict[str, Any]:
    """Estimate cost of a DI analyze call (used by Analyzer Compare).

    DI bills per 1,000 pages at a flat rate per prebuilt analyzer. Pricing
    lives in `pricing.di.per_1000_pages`; unknown analyzers fall back to
    the `_default` row.
    """
    p = _pricing()
    bd = _empty_breakdown()
    pages = _count_pages_di(payload)
    di = p.get("di", {}) or {}
    per_1000 = di.get("per_1000_pages", {}) or {}
    rate_per_1000 = float(per_1000.get(analyzer_id, per_1000.get("_default", 10.0)))
    amount = (pages / 1000.0) * rate_per_1000
    _add_component(
        bd,
        f"DI {analyzer_id} ({pages} pages @ ${rate_per_1000:.2f}/1k)",
        qty=pages,
        unit="page",
        amount=amount,
    )
    bd["inputs"] = {
        "pages": pages,
        "di_analyzer_id": analyzer_id,
        "rate_per_1000": rate_per_1000,
    }
    return bd


# ── Composed pipeline cost (CU + local compute) ────────────────────────────


def estimate_pipeline_cost(
    payload: dict[str, Any],
    *,
    include_compute: bool = True,
) -> dict[str, Any]:
    """Composed cost for a full SOV pipeline run.

    Wraps `estimate_cu_cost` and adds a flat local-compute line item for
    LibreOffice render + TIFF rasterization. Most cost comes from CU; the
    local-compute number is a placeholder so the breakdown is complete.
    """
    p = _pricing()
    bd = estimate_cu_cost(payload)
    if include_compute:
        compute = float((p.get("compute") or {}).get("per_pipeline_run", 0.0))
        if compute > 0:
            _add_component(
                bd,
                "Local compute (render + rasterize)",
                qty=1,
                unit="run",
                amount=compute,
            )
    return bd


# ── Aggregate helpers (for multi-call Analyzer Compare runs) ───────────────


def sum_breakdowns(breakdowns: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Combine N cost breakdowns into one. Components are preserved verbatim
    (prefixed by source) so the UI can render them as a flat list."""
    out = _empty_breakdown()
    for bd in breakdowns:
        if not bd:
            continue
        out["total"] = _round(out["total"] + float(bd.get("total", 0.0)))
        out["components"].extend(bd.get("components") or [])
    return out
