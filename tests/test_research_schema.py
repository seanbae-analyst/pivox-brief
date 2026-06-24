"""Validation tests for the qualitative schema (engine/research_schema.py).

Locks the two guarantees that make the qualitative layer trustworthy: themes are
restricted to the controlled vocabulary (out-of-vocabulary is rejected), and every
confidence is bounded to [0, 1].
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engine.research_schema import QualitativeBlock, ResearchTheme


def test_qualitative_block_round_trips_to_json():
    b = QualitativeBlock(
        guidance={"direction": "raised", "detail": "FY27 revenue guide up", "confidence": 0.8, "source_url": "http://x"},
        tone={"label": "confident", "confidence": 0.7},
        themes=[{"theme": "capex_investment", "direction": "positive",
                 "evidence": "data-center capex ramp cited", "confidence": 0.82, "source_url": "http://x"}],
        risk_factors=[{"summary": "revenue concentrated in a few large customers", "source_url": "http://x"}],
        sources=["http://x"],
    )
    d = b.model_dump(mode="json")
    assert d["guidance"]["direction"] == "raised"
    assert d["themes"][0]["theme"] == "capex_investment"
    assert d["tone"]["label"] == "confident"


def test_theme_rejects_out_of_vocabulary():
    with pytest.raises(ValidationError):
        ResearchTheme(theme="ai_bubble", direction="negative", evidence="x", confidence=0.5, source_url="u")


def test_confidence_must_be_in_unit_interval():
    with pytest.raises(ValidationError):
        ResearchTheme(theme="demand_strength", direction="positive", evidence="x", confidence=1.5, source_url="u")


def test_empty_block_is_valid():
    b = QualitativeBlock()
    assert b.themes == [] and b.guidance is None
