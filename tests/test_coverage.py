"""Tests for the coverage manifest (engine/research_pack.coverage_manifest).

Covered items must reflect what actually resolved for the issuer; the partial and
structurally-out lists are standing limits that are always present.
"""

from __future__ import annotations

from engine.edgar import CompanyProfile
from engine.research_pack import ResearchPack, coverage_manifest


def _profile():
    return CompanyProfile(cik="0000320193", name="Apple Inc.", tickers=["AAPL"],
                          exchanges=["Nasdaq"], sic_description="Electronic Computers")


def test_manifest_reflects_present_layers():
    pack = ResearchPack(
        query="AAPL", language="en", profile=_profile(),
        trend=["q"], filings=["f"], news=["n"],
        quant={"valuation": {"pe_ttm": 10}, "price": {"last_close": 1}},
        qualitative={"themes": ["t"]},
    )
    cov = coverage_manifest(pack)
    joined = " ".join(cov["covered"])
    assert "Fundamentals" in joined
    assert "Valuation" in joined
    assert "Qualitative" in joined
    assert "Price action" in joined
    # structural limits are always declared
    assert any("consensus" in s.lower() for s in cov["structurally_out"])
    assert any("transcript" in s.lower() for s in cov["structurally_out"])


def test_manifest_minimal_pack_has_no_false_coverage():
    pack = ResearchPack(query="X", language="en",
                        profile=CompanyProfile(cik="1", name="X", tickers=["X"], exchanges=[], sic_description=""))
    cov = coverage_manifest(pack)
    assert cov["covered"] == []                  # nothing resolved → claim nothing
    assert cov["partial"] and cov["structurally_out"]
