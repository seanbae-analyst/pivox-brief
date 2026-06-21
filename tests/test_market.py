"""Market-reaction analysis (L1/L2) — pure, offline (mock reactions)."""

from engine.analysis import divergences, reaction_by_lean, signal_lean
from engine.schema import (
    Confidence,
    EarningsSignal,
    EarningsSignalDraft,
    GuidanceDirection,
    Metric,
    Tone,
)
from engine.taxonomy import KeyTheme


def _sig(ticker, guidance, tone):
    d = EarningsSignalDraft(
        ticker=ticker,
        period="Q1",
        call_date="2026-01-01",
        headline_metrics=[Metric(name="total_revenue", value_usd=1e9)],
        guidance_direction=guidance,
        key_themes=[KeyTheme.demand_strength],
        risk_factors=[],
        management_tone=tone,
        confidence=Confidence(metrics=0.9, guidance=0.9, tone=0.9, themes=0.9),
    )
    return EarningsSignal.model_validate({**d.model_dump(), "needs_review": False})


def test_signal_lean():
    assert signal_lean(_sig("A", GuidanceDirection.raised, Tone.confident)) == 1
    assert signal_lean(_sig("B", GuidanceDirection.lowered, Tone.defensive)) == -1
    assert signal_lean(_sig("C", GuidanceDirection.maintained, Tone.mixed)) == 0


def test_reaction_by_lean_averages():
    sigs = [
        _sig("A", GuidanceDirection.raised, Tone.confident),     # positive
        _sig("B", GuidanceDirection.maintained, Tone.mixed),     # neutral
    ]
    rx = {"A": {"event_return_pct": 10.0}, "B": {"event_return_pct": -2.0}}
    by = reaction_by_lean(sigs, rx)
    assert by["positive"] == 10.0 and by["neutral"] == -2.0


def test_divergence_positive_signal_negative_move():
    sigs = [_sig("WMT", GuidanceDirection.maintained, Tone.confident)]  # lean +1
    rx = {"WMT": {"event_return_pct": -8.0}}
    d = divergences(sigs, rx)
    assert len(d) == 1 and d[0]["ticker"] == "WMT" and d[0]["lean"] == "positive"


def test_no_divergence_when_aligned():
    sigs = [_sig("AMD", GuidanceDirection.raised, Tone.confident)]
    rx = {"AMD": {"event_return_pct": 15.0}}
    assert divergences(sigs, rx) == []
