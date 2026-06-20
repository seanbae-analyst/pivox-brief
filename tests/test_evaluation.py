"""Evaluation-harness tests (§7) — synthetic, fully offline."""

from engine.evaluation import score_record, target_sentence, threshold_sweep
from engine.schema import (
    Confidence,
    EarningsSignal,
    EarningsSignalDraft,
    GuidanceDirection,
    Metric,
    Tone,
)
from engine.taxonomy import KeyTheme


def _sig(
    *,
    conf=(0.9, 0.9, 0.9, 0.9),
    themes=(KeyTheme.demand_strength,),
    guidance=GuidanceDirection.raised,
    tone=Tone.confident,
    rev=82_000_000_000.0,
):
    draft = EarningsSignalDraft(
        ticker="X",
        period="Q1",
        call_date="2026-01-01",
        headline_metrics=[Metric(name="total_revenue", value_usd=rev)],
        guidance_direction=guidance,
        key_themes=list(themes),
        risk_factors=[],
        management_tone=tone,
        confidence=Confidence(metrics=conf[0], guidance=conf[1], tone=conf[2], themes=conf[3]),
    )
    return EarningsSignal.model_validate({**draft.model_dump(), "needs_review": False})


GOLD = {
    "ticker": "X",
    "period": "Q1",
    "guidance_direction": "raised",
    "management_tone": "confident",
    "key_themes": ["demand_strength"],
    "metrics": {"total_revenue": 82_000_000_000},
}


def test_perfect_match_scores_one():
    s = score_record(_sig(), GOLD)
    assert s.guidance_correct and s.tone_correct
    assert s.themes_f1 == 1.0 and s.metrics_accuracy == 1.0
    assert s.overall == 1.0


def test_wrong_guidance_and_metric():
    s = score_record(_sig(guidance=GuidanceDirection.lowered, rev=50_000_000_000.0), GOLD)
    assert s.guidance_correct is False
    assert s.metrics_accuracy == 0.0


def test_metric_within_tolerance_counts():
    # 81.6B vs gold 82B — ~0.5%, inside the 2% tolerance.
    s = score_record(_sig(rev=81_600_000_000.0), GOLD)
    assert s.metrics_accuracy == 1.0


def test_themes_precision_recall():
    s = score_record(_sig(themes=(KeyTheme.demand_strength, KeyTheme.m_and_a)), GOLD)
    assert s.themes_precision == 0.5  # 1 of 2 predicted are correct
    assert s.themes_recall == 1.0     # the 1 gold theme was found


def test_threshold_sweep_auto_rate_monotonic():
    pairs = [
        (_sig(conf=(0.95, 0.95, 0.95, 0.95)), GOLD),
        (_sig(conf=(0.60, 0.90, 0.90, 0.90)), GOLD),
    ]
    rows = {r.threshold: r for r in threshold_sweep(pairs, (0.70, 0.90))}
    assert rows[0.70].auto_rate >= rows[0.90].auto_rate
    assert rows[0.90].auto_rate == 0.5  # only the high-confidence record clears 0.90


def test_target_sentence_runs():
    assert "auto-processed" in target_sentence([(_sig(), GOLD)])
