"""Lightweight rule engine for the Pro Mode fraud demo.

Pro-mode CU analyzers don't emit confidence scores or grounding, so we
layer a small set of deterministic rules over the structured fields the
pro_claims analyzer extracted. The rules are intentionally narrow: each
one targets a single, explainable signal that a fraud investigator would
flag manually.

The rule engine is also used by the unit tests, so it must remain pure —
no I/O, no network, no Azure SDK calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from app.schemas.pro import FraudSignal


# ── Policy facts ────────────────────────────────────────────────────────────
# Hard-coded for the demo. In production these would come from a policy-lookup
# service keyed off the policy number.
@dataclass(frozen=True)
class PolicyFacts:
    policy_number: str = "PA-7421-2026"
    named_insured: str = "Sarah J. Whitfield"
    vin: str = "2T2BZMCA5KC192847"
    effective: date = date(2026, 1, 15)
    expiration: date = date(2027, 1, 15)
    collision_sub_limit: float = 12000.0
    collision_deductible: float = 1000.0


POLICY = PolicyFacts()


# ── Helpers ─────────────────────────────────────────────────────────────────
def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    v = value.strip()
    # Accept ISO YYYY-MM-DD and a few common variants.
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    # Last-ditch: pull yyyy-mm-dd out of a longer string.
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _norm_vin(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _norm_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    # Strip honorifics, suffixes, punctuation; collapse whitespace.
    v = re.sub(r"[.,;]", " ", value).strip()
    v = re.sub(r"\s+", " ", v)
    parts = [p for p in v.split(" ") if p.lower() not in {"mr", "mrs", "ms", "dr", "jr", "sr"}]
    return " ".join(parts).lower() if parts else None


def _names_match(a: Optional[str], b: Optional[str]) -> bool:
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Last-name match + first-initial match is enough for the demo.
    pa, pb = na.split(), nb.split()
    if pa and pb and pa[-1] == pb[-1] and pa[0][:1] == pb[0][:1]:
        return True
    return False


# ── Rules ───────────────────────────────────────────────────────────────────
def _rule_vin_mismatch(
    claim_vin: Optional[str],
    policy_vin: str = POLICY.vin,
) -> Optional[FraudSignal]:
    nv = _norm_vin(claim_vin)
    if not nv:
        return None
    if nv == _norm_vin(policy_vin):
        return None
    return FraudSignal(
        rule_id="VIN_MISMATCH",
        severity="medium",
        title="VIN on claim docs does not match policy VIN",
        evidence=f"Claim VIN '{claim_vin}' vs policy VIN '{policy_vin}'.",
        source_documents=["FNOL or repair estimate", "auto_policy.pdf"],
        weight=25,
    )


def _rule_policy_number_mismatch(
    claim_policy_number: Optional[str],
    policy_number: str = POLICY.policy_number,
) -> Optional[FraudSignal]:
    if not claim_policy_number:
        return None
    a = re.sub(r"\s+", "", claim_policy_number).upper()
    b = re.sub(r"\s+", "", policy_number).upper()
    if a == b:
        return None
    return FraudSignal(
        rule_id="POLICY_NUMBER_MISMATCH",
        severity="medium",
        title="Policy number on claim does not match reference policy",
        evidence=f"Claim policy '{claim_policy_number}' vs reference policy '{policy_number}'.",
        source_documents=["FNOL or repair estimate", "auto_policy.pdf"],
        weight=20,
    )


def _rule_name_mismatch(
    claimant_name: Optional[str],
    named_insured: str = POLICY.named_insured,
) -> Optional[FraudSignal]:
    if not claimant_name:
        return None
    if _names_match(claimant_name, named_insured):
        return None
    return FraudSignal(
        rule_id="NAME_MISMATCH",
        severity="medium",
        title="Claimant name does not match named insured on the policy",
        evidence=f"Claimant '{claimant_name}' vs named insured '{named_insured}'.",
        source_documents=["FNOL", "auto_policy.pdf"],
        weight=20,
    )


def _rule_totals_exceed_sublimit(
    estimated_total: Optional[float],
    sub_limit: float = POLICY.collision_sub_limit,
) -> Optional[FraudSignal]:
    if estimated_total is None or estimated_total <= sub_limit:
        return None
    over = estimated_total - sub_limit
    return FraudSignal(
        rule_id="TOTALS_EXCEED_SUBLIMIT",
        severity="high",
        title="Repair estimate exceeds policy collision sub-limit",
        evidence=(
            f"Estimate total ${estimated_total:,.2f} exceeds policy collision "
            f"sub-limit ${sub_limit:,.2f} by ${over:,.2f}."
        ),
        source_documents=["repair_estimate.pdf", "auto_policy.pdf"],
        weight=35,
    )


def _rule_estimate_date_before_loss(
    estimate_date: Optional[str],
    date_of_loss: Optional[str],
) -> Optional[FraudSignal]:
    de = _parse_date(estimate_date)
    dl = _parse_date(date_of_loss)
    if not de or not dl:
        return None
    if de >= dl:
        return None
    days = (dl - de).days
    return FraudSignal(
        rule_id="DATE_IMPLAUSIBLE",
        severity="high",
        title="Repair estimate is dated before the date of loss",
        evidence=(
            f"Estimate dated {de.isoformat()} is {days} day(s) BEFORE the date "
            f"of loss {dl.isoformat()} reported on the FNOL — the policy "
            f"excludes pre-existing damage."
        ),
        source_documents=["repair_estimate.pdf", "FNOL claim_form.pdf"],
        weight=35,
    )


def _rule_out_of_policy_period(
    date_of_loss: Optional[str],
    effective: date = POLICY.effective,
    expiration: date = POLICY.expiration,
) -> Optional[FraudSignal]:
    dl = _parse_date(date_of_loss)
    if not dl:
        return None
    if effective <= dl <= expiration:
        return None
    return FraudSignal(
        rule_id="DATE_OUTSIDE_POLICY_PERIOD",
        severity="high",
        title="Date of loss falls outside the policy period",
        evidence=(
            f"Date of loss {dl.isoformat()} is outside the policy period "
            f"{effective.isoformat()} .. {expiration.isoformat()}."
        ),
        source_documents=["FNOL claim_form.pdf", "auto_policy.pdf"],
        weight=30,
    )


# ── Public entrypoint ──────────────────────────────────────────────────────
def evaluate(
    *,
    claimant_name: Optional[str] = None,
    policy_number: Optional[str] = None,
    vin: Optional[str] = None,
    date_of_loss: Optional[str] = None,
    estimated_total: Optional[float] = None,
    estimate_date: Optional[str] = None,
) -> list[FraudSignal]:
    """Run every rule against the supplied (already-extracted) fields and
    return the signals that fired."""
    candidates = [
        _rule_vin_mismatch(vin),
        _rule_policy_number_mismatch(policy_number),
        _rule_name_mismatch(claimant_name),
        _rule_totals_exceed_sublimit(estimated_total),
        _rule_estimate_date_before_loss(estimate_date, date_of_loss),
        _rule_out_of_policy_period(date_of_loss),
    ]
    return [s for s in candidates if s is not None]


def blend_risk_score(
    cu_signals: list[FraudSignal],
    rule_signals: list[FraudSignal],
) -> tuple[int, str]:
    """Combine CU-reasoning signals and rule signals into a 0..100 score.

    Rule signals are deterministic and weighted; CU signals are softer and
    weighted lower. The two are summed and clamped.
    """
    score = 0
    for s in rule_signals:
        score += s.weight
    for s in cu_signals:
        # CU signals carry their own weight, but we discount them by 30% to
        # reflect that they're LLM-derived (no confidence/grounding).
        score += int(round(s.weight * 0.7))
    score = max(0, min(100, score))
    if score >= 60:
        band = "high"
    elif score >= 30:
        band = "medium"
    else:
        band = "low"
    return score, band
