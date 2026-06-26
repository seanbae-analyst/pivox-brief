"""Offline tests for the management-tone trajectory (engine/tone_trajectory.py).

The scorer + trajectory builder are pure (no network). Locks the Loughran-McDonald-style density
math, the oldest→newest direction, and graceful degradation (<2 periods → None). Network fetch
(``tone_trajectory``) is the gated I/O wrapper and is not exercised here (no network in tests).
"""

from __future__ import annotations

from engine.tone_trajectory import build_trajectory, score_tone


def test_score_tone_counts_densities():
    s = score_tone("Growth was strong and revenue increased; margins improved.")
    assert s["positive_density"] > 0
    assert s["negative_density"] == 0.0
    assert s["net_tone"] == s["positive_density"]  # no negatives


def test_score_tone_negative_and_uncertainty():
    s = score_tone("Results may decline; litigation risk and uncertain demand could cause losses.")
    assert s["negative_density"] > 0
    assert s["uncertainty_density"] > 0
    assert s["net_tone"] < 0


def test_score_tone_empty_is_zero():
    s = score_tone("")
    assert s == {"words": 0, "negative_density": 0.0, "uncertainty_density": 0.0,
                 "positive_density": 0.0, "net_tone": 0.0}


def test_build_trajectory_direction_rising():
    docs = [
        ("CY2025Q3", "Demand was weak; sales declined and margins deteriorated amid litigation."),
        ("CY2025Q4", "Conditions stabilized over the period across the business segments."),
        ("CY2026Q1", "Growth was strong, revenue increased to a record, and margins improved."),
    ]
    t = build_trajectory(docs)
    assert t["net_tone_direction"] == "rising"
    assert len(t["periods"]) == 3
    assert t["periods"][0]["period"] == "CY2025Q3"


def test_build_trajectory_none_when_too_few():
    assert build_trajectory([]) is None
    assert build_trajectory([("Q1", "only one quarter of text here")]) is None
    # blank docs are dropped → still too few
    assert build_trajectory([("Q1", "real text strong growth"), ("Q2", "   ")]) is None


def test_observations_descriptive_only():
    docs = [("Q1", "weak decline losses litigation"), ("Q2", "strong growth record improved")]
    t = build_trajectory(docs)
    blob = " ".join(t["observations"]).lower()
    for banned in ("buy", "sell", "recommend", "should", "avoid", "verdict"):
        assert banned not in blob
    assert "auditable" in t["note"].lower()
