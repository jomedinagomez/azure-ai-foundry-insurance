"""Unit tests for the fraud-rules engine. No network, no Azure calls."""
from __future__ import annotations

from app.services import fraud_rules
from app.services.fraud_rules import POLICY


def _ids(signals) -> set[str]:
    return {s.rule_id for s in signals}


def test_clean_case_emits_no_signals():
    signals = fraud_rules.evaluate(
        claimant_name=POLICY.named_insured,
        policy_number=POLICY.policy_number,
        vin=POLICY.vin,
        date_of_loss="2026-03-14",
        estimated_total=8500.00,
        estimate_date="2026-03-16",
    )
    assert signals == []


def test_vin_mismatch_fires():
    signals = fraud_rules.evaluate(vin="2T2BZMCA5KC192947")  # one char different
    assert "VIN_MISMATCH" in _ids(signals)


def test_vin_match_ignores_punctuation():
    signals = fraud_rules.evaluate(vin=" 2t2bzmca5KC192847 ")
    assert "VIN_MISMATCH" not in _ids(signals)


def test_policy_number_mismatch_fires():
    signals = fraud_rules.evaluate(policy_number="PA-9999-2026")
    assert "POLICY_NUMBER_MISMATCH" in _ids(signals)


def test_claimant_name_mismatch_fires():
    signals = fraud_rules.evaluate(claimant_name="John Doe")
    assert "NAME_MISMATCH" in _ids(signals)


def test_claimant_name_with_middle_initial_does_not_fire():
    signals = fraud_rules.evaluate(claimant_name="Sarah Whitfield")
    assert "NAME_MISMATCH" not in _ids(signals)


def test_totals_exceed_sublimit_fires():
    signals = fraud_rules.evaluate(estimated_total=18940.00)
    s = next(x for x in signals if x.rule_id == "TOTALS_EXCEED_SUBLIMIT")
    assert s.severity == "high"
    assert "12,000" in s.evidence
    assert "18,940" in s.evidence


def test_totals_within_sublimit_does_not_fire():
    signals = fraud_rules.evaluate(estimated_total=11500.00)
    assert "TOTALS_EXCEED_SUBLIMIT" not in _ids(signals)


def test_estimate_before_loss_fires():
    signals = fraud_rules.evaluate(
        date_of_loss="2026-03-14",
        estimate_date="2026-03-09",
    )
    s = next(x for x in signals if x.rule_id == "DATE_IMPLAUSIBLE")
    assert s.severity == "high"
    assert "5 day" in s.evidence


def test_estimate_same_day_as_loss_does_not_fire():
    signals = fraud_rules.evaluate(
        date_of_loss="2026-03-14",
        estimate_date="2026-03-14",
    )
    assert "DATE_IMPLAUSIBLE" not in _ids(signals)


def test_date_outside_policy_period_fires():
    signals = fraud_rules.evaluate(date_of_loss="2025-12-30")
    assert "DATE_OUTSIDE_POLICY_PERIOD" in _ids(signals)


def test_blend_risk_score_clean():
    score, band = fraud_rules.blend_risk_score([], [])
    assert score == 0
    assert band == "low"


def test_blend_risk_score_fraud_variant():
    rule_signals = fraud_rules.evaluate(
        vin="2T2BZMCA5KC192947",
        date_of_loss="2026-03-14",
        estimated_total=18940.00,
        estimate_date="2026-03-09",
    )
    score, band = fraud_rules.blend_risk_score([], rule_signals)
    # VIN(25) + TOTALS(35) + DATE(35) = 95
    assert score >= 70
    assert band == "high"
