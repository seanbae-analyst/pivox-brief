"""Offline tests for filing text reduction + section slicing (engine/filings.py).

No network: a synthetic 10-K-shaped HTML exercises the hard case — the table of
contents names "Item 1A. Risk Factors" before the real section, and the slicer must
return the real (long) section, not the TOC stub.
"""

from __future__ import annotations

from engine import filings

SAMPLE_HTML = (
    "<html><body>"
    "<table>"
    "<tr><td>Item 1A. Risk Factors</td><td>15</td></tr>"
    "<tr><td>Item 1B. Unresolved Staff Comments</td><td>30</td></tr>"
    "<tr><td>Item 7. Management's Discussion and Analysis</td><td>40</td></tr>"
    "</table>"
    "<p>Item 1A. Risk Factors</p>"
    "<p>Our business depends on demand for AI accelerators, concentrated in a few customers. "
    + ("Supply constraints could materially affect results. " * 60)
    + "</p>"
    "<p>Item 1B. Unresolved Staff Comments</p><p>None.</p>"
    "<p>Item 7. Management's Discussion and Analysis of Financial Condition</p>"
    "<p>Revenue rose year over year on data center strength. " + ("Margin expanded. " * 60) + "</p>"
    "<p>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</p>"
    "</body></html>"
)


def test_html_to_text_strips_tags_and_unescapes():
    t = filings.html_to_text("<p>Hello <b>world</b> &amp; co</p>")
    assert "Hello world & co" in t
    assert "<" not in t and ">" not in t


def test_risk_factors_returns_real_section_not_toc():
    text = filings.html_to_text(SAMPLE_HTML)
    rf = filings.risk_factors(text)
    assert "AI accelerators" in rf                 # real section content present
    assert "Supply constraints" in rf
    assert "Unresolved Staff Comments" not in rf   # stopped at Item 1B
    assert len(rf) > 1000                          # not the tiny TOC stub


def test_mda_slices_between_item7_and_7a():
    text = filings.html_to_text(SAMPLE_HTML)
    m = filings.mda(text)
    assert "data center strength" in m
    assert "Quantitative and Qualitative" not in m  # stopped at Item 7A


def test_slice_section_empty_without_start_marker():
    assert filings.slice_section("nothing relevant here", [r"item\s*1a"], [r"item\s*1b"]) == ""
