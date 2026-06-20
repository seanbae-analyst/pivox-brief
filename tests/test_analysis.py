"""Cross-company analysis tests (§2) — offline."""

from engine.analysis import (
    analyze,
    guidance_distribution,
    metric_ranking,
    review_rate,
    theme_frequency,
)
from engine.schema import (
    Confidence,
    EarningsSignal,
    EarningsSignalDraft,
    GuidanceDirection,
    Metric,
    Tone,
)
from engine.taxonomy import KeyTheme


def _sig(ticker, themes, guidance, tone, rev_yoy, needs_review=False):
    draft = EarningsSignalDraft(
        ticker=ticker,
        period="Q1",
        call_date="2026-01-01",
        headline_metrics=[Metric(name="total_revenue", value_usd=1e9, yoy_pct=rev_yoy)],
        guidance_direction=guidance,
        key_themes=list(themes),
        risk_factors=[],
        management_tone=tone,
        confidence=Confidence(metrics=0.9, guidance=0.9, tone=0.9, themes=0.9),
    )
    return EarningsSignal.model_validate({**draft.model_dump(), "needs_review": needs_review})


SIGNALS = [
    _sig("AAA", [KeyTheme.demand_strength, KeyTheme.new_product_ramp], GuidanceDirection.raised, Tone.confident, 80, False),
    _sig("BBB", [KeyTheme.demand_strength, KeyTheme.supply_constraint], GuidanceDirection.raised, Tone.cautious, 40, True),
    _sig("CCC", [KeyTheme.demand_weakness], GuidanceDirection.lowered, Tone.defensive, 5, True),
]


def test_theme_frequency_orders_by_count():
    tf = dict(theme_frequency(SIGNALS))
    assert tf["demand_strength"] == 2
    assert theme_frequency(SIGNALS)[0][0] == "demand_strength"


def test_guidance_distribution():
    assert guidance_distribution(SIGNALS) == {"raised": 2, "lowered": 1}


def test_metric_ranking_desc():
    rank = metric_ranking(SIGNALS, "total_revenue", "yoy_pct")
    assert [t for t, _ in rank] == ["AAA", "BBB", "CCC"]


def test_review_rate():
    assert review_rate(SIGNALS) == (2, 3, 2 / 3)


def test_analyze_headlines_nonempty():
    intel = analyze(SIGNALS)
    assert intel.n == 3
    assert any("Fastest revenue growth: AAA" in h for h in intel.headlines)
