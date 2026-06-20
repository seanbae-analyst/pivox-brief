"""Cross-run consistency tests (§6 ③) — pure logic, no API calls."""

from engine.confidence import agreement, derive_needs_review, finalize
from engine.schema import (
    Confidence,
    EarningsSignalDraft,
    GuidanceDirection,
    Metric,
    Tone,
)
from engine.taxonomy import KeyTheme


def _draft(**over):
    base = dict(
        ticker="NVDA",
        period="Q1 FY2027",
        call_date="2026-05-20",
        headline_metrics=[Metric(name="total_revenue", value_usd=81_615_000_000, yoy_pct=85.0)],
        guidance_direction=GuidanceDirection.raised,
        guidance_detail=None,
        key_themes=[KeyTheme.demand_strength, KeyTheme.new_product_ramp],
        risk_factors=["export controls"],
        management_tone=Tone.confident,
        confidence=Confidence(metrics=0.95, guidance=0.95, tone=0.95, themes=0.95),
    )
    base.update(over)
    return EarningsSignalDraft(**base)


def test_identical_drafts_fully_agree():
    ag = agreement(_draft(), _draft())
    assert ag.score == 1.0
    assert ag.consistent is True


def test_metric_value_within_tolerance_counts_as_agreement():
    # 81.615B vs 81.6B — well within the 2% default tolerance.
    a = _draft()
    b = _draft(headline_metrics=[Metric(name="total_revenue", value_usd=81_600_000_000, yoy_pct=85.0)])
    assert agreement(a, b).metrics_overlap == 1.0


def test_disagreement_lowers_score():
    a = _draft()
    b = _draft(
        guidance_direction=GuidanceDirection.maintained,  # differs
        key_themes=[KeyTheme.demand_strength],            # 1/2 overlap → jaccard 0.5
    )
    ag = agreement(a, b)
    assert ag.guidance_match is False
    assert ag.themes_jaccard == 0.5
    assert ag.score < 1.0


def test_inconsistency_forces_review_even_when_confident():
    # High self-confidence, no sanity warnings — would auto-approve on its own...
    draft = _draft()
    assert derive_needs_review(draft, warnings=[]) is False
    # ...but a low-agreement cross-run result must force review (§6 ③).
    a = _draft()
    b = _draft(guidance_direction=GuidanceDirection.lowered, management_tone=Tone.cautious,
               key_themes=[KeyTheme.macro_headwind])
    ag = agreement(a, b)
    assert ag.consistent is False
    signal, _ = finalize(draft, ag)
    assert signal.needs_review is True
