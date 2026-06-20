"""Schema + taxonomy tests — fully offline, no API calls."""

import pytest
from pydantic import ValidationError

from engine.schema import (
    Confidence,
    EarningsSignal,
    EarningsSignalDraft,
    GuidanceDirection,
    Metric,
    Tone,
)
from engine.taxonomy import KeyTheme, other_rate


def _draft(**over):
    base = dict(
        ticker="NVDA",
        period="Q1 FY2027",
        call_date="2026-05-20",
        headline_metrics=[
            Metric(name="total_revenue", value_usd=81_615_000_000, yoy_pct=85.0, qoq_pct=20.0)
        ],
        guidance_direction=GuidanceDirection.raised,
        guidance_detail="Q2 revenue guided higher",
        key_themes=[KeyTheme.demand_strength, KeyTheme.new_product_ramp],
        risk_factors=["export controls"],
        management_tone=Tone.confident,
        confidence=Confidence(metrics=0.95, guidance=0.90, tone=0.92, themes=0.88),
    )
    base.update(over)
    return base


def test_draft_constructs():
    d = EarningsSignalDraft(**_draft())
    assert d.ticker == "NVDA"
    assert d.confidence.min_dim() == 0.88


def test_enum_coercion_from_strings():
    d = EarningsSignalDraft(**_draft(guidance_direction="raised", management_tone="confident"))
    assert d.guidance_direction is GuidanceDirection.raised
    assert d.management_tone is Tone.confident


def test_key_themes_reject_unknown():
    # Out-of-vocabulary themes are unrepresentable (§4).
    with pytest.raises(ValidationError):
        EarningsSignalDraft(**_draft(key_themes=["totally_made_up_theme"]))


def test_confidence_bounds_enforced():
    with pytest.raises(ValidationError):
        Confidence(metrics=1.5, guidance=0.9, tone=0.9, themes=0.9)


def test_final_signal_carries_needs_review():
    sig = EarningsSignal(**_draft(), needs_review=True)
    assert sig.needs_review is True


def test_other_rate():
    assert other_rate([KeyTheme.other, KeyTheme.demand_strength]) == 0.5
    assert other_rate([]) == 0.0
