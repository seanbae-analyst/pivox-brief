"""Offline tests for risk-factor delta logic (engine/risk_delta.py).

Locks header extraction (pull summary bullets, drop category headers) and the fuzzy diff
(reworded risks match; genuinely new/dropped ones surface). No network — synthetic Item 1A.
"""

from __future__ import annotations

from engine.risk_delta import _similar, diff_risks, extract_risk_headers

SAMPLE = """
Item 1A. Risk Factors
The following risks could harm our business, financial condition or results of operations.
Risk Factors Summary
Risks Related to Our Industry and Markets
Competition could adversely impact our market share and financial results.
The semiconductor industry is highly cyclical and downturns may adversely affect us.
Risks Related to Regulatory Matters
We are subject to export controls that may adversely impact sales of our products in China.
Risk Factors
Competition could adversely impact our market share and financial results.
Our platforms experience rapid changes in technology and customer requirements.
"""


def test_extract_pulls_bullets_excludes_categories():
    h = extract_risk_headers(SAMPLE)
    assert any("Competition could adversely" in x for x in h)
    assert any("highly cyclical" in x for x in h)
    assert any("export controls" in x for x in h)
    assert not any(x.lower().startswith("risks related") for x in h)  # category headers dropped


def test_diff_detects_added_and_removed():
    current = [
        "Competition could adversely impact our market share and results.",
        "New AI export restrictions to China may reduce demand for our products.",
    ]
    prior = [
        "Competition could adversely impact our market share and financial results.",
        "Reliance on third-party foundries could disrupt our manufacturing supply.",
    ]
    d = diff_risks(current, prior)
    assert any("export restrictions" in a for a in d["added"])   # genuinely new
    assert any("foundries" in r for r in d["removed"])           # dropped this year
    assert not any("Competition" in a for a in d["added"])       # reworded match → not "added"


def test_similar_matches_reworded_lines():
    assert _similar(
        "Competition could adversely impact our market share and financial results.",
        "Competition could adversely impact our market share and results.",
    ) >= 0.5
    assert _similar("export controls in China", "reliance on third-party foundries") < 0.5
