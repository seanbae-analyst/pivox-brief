"""Schema v1 ratios — model, eval scoring, analysis ranking (offline)."""

from engine.analysis import ratio_ranking
from engine.evaluation import score_ratios, score_record
from engine.schema import (
    Confidence,
    EarningsSignal,
    EarningsSignalDraft,
    GuidanceDirection,
    Metric,
    Ratio,
    RatioUnit,
    Tone,
)
from engine.taxonomy import KeyTheme


def _sig(ticker, ratios, rev_yoy=50.0):
    draft = EarningsSignalDraft(
        ticker=ticker,
        period="Q1",
        call_date="2026-01-01",
        headline_metrics=[Metric(name="total_revenue", value_usd=1e9, yoy_pct=rev_yoy)],
        ratios=ratios,
        guidance_direction=GuidanceDirection.raised,
        key_themes=[KeyTheme.demand_strength],
        risk_factors=[],
        management_tone=Tone.confident,
        confidence=Confidence(metrics=0.9, guidance=0.9, tone=0.9, themes=0.9),
    )
    return EarningsSignal.model_validate({**draft.model_dump(), "needs_review": False})


def test_ratio_unit_enum_coercion():
    r = Ratio(name="gross_margin", value=74.9, unit="percent")
    assert r.unit is RatioUnit.percent


def test_ratios_default_empty_is_backcompat():
    assert _sig("X", []).ratios == []


def test_score_ratios_percent_point_tolerance():
    s = _sig("X", [Ratio(name="gross_margin", value=74.9, unit=RatioUnit.percent)])
    assert score_ratios(s, {"gross_margin": 75.5})[2] == 1.0   # within 1.0pt
    assert score_ratios(s, {"gross_margin": 80.0})[2] == 0.0   # beyond 1.0pt


def test_score_ratios_per_share_rel_tolerance():
    s = _sig("X", [Ratio(name="eps", value=1.37, unit=RatioUnit.per_share)])
    assert score_ratios(s, {"eps": 1.38})[2] == 1.0            # <2%


def test_score_record_grades_ratios():
    s = _sig("X", [Ratio(name="gross_margin", value=55.0, unit=RatioUnit.percent)])
    gold = {
        "ticker": "X", "period": "Q1", "guidance_direction": "raised",
        "management_tone": "confident", "key_themes": ["demand_strength"],
        "metrics": {}, "ratios": {"gross_margin": 55.0},
    }
    sc = score_record(s, gold)
    assert sc.ratios_total == 1 and sc.ratios_accuracy == 1.0


def test_ratio_ranking_desc_skips_undisclosed():
    sigs = [
        _sig("A", [Ratio(name="gross_margin", value=55.0, unit=RatioUnit.percent)]),
        _sig("B", [Ratio(name="gross_margin", value=74.9, unit=RatioUnit.percent)]),
        _sig("C", []),
    ]
    assert [t for t, _ in ratio_ranking(sigs, "gross_margin")] == ["B", "A"]
