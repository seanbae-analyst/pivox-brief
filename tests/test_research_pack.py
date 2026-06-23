"""Research-pack assembly — pure, offline. Trend derivation (margins, YoY) and the
Markdown renderer, exercised on synthetic EDGAR series (no network)."""

from engine.edgar import CompanyProfile, FactPoint, Filing, FinancialSeries
from engine.news import NewsItem
from engine.research_pack import (
    ResearchPack,
    _language_for,
    build_trend,
    render_markdown,
)


def _series(concept, triples):
    """triples: list of (frame, end, val) -> FinancialSeries."""
    return FinancialSeries(
        concept=concept,
        points=[FactPoint(end=e, val=v, fy=None, fp=None, form="10-Q", frame=f) for f, e, v in triples],
    )


# 8 quarters of revenue so the last 4 each have a year-ago comparison.
REV = _series("Revenues", [
    ("CY2024Q1", "2024-03-31", 100.0), ("CY2024Q2", "2024-06-30", 110.0),
    ("CY2024Q3", "2024-09-30", 120.0), ("CY2024Q4", "2024-12-31", 130.0),
    ("CY2025Q1", "2025-03-31", 120.0), ("CY2025Q2", "2025-06-30", 132.0),
    ("CY2025Q3", "2025-09-30", 150.0), ("CY2025Q4", "2025-12-31", 169.0),
])
GP = _series("GrossProfit", [  # 50% of revenue on the last 4 ends
    ("CY2025Q1", "2025-03-31", 60.0), ("CY2025Q2", "2025-06-30", 66.0),
    ("CY2025Q3", "2025-09-30", 75.0), ("CY2025Q4", "2025-12-31", 84.5),
])
EPS = _series("EarningsPerShareDiluted", [
    ("CY2025Q1", "2025-03-31", 1.0), ("CY2025Q2", "2025-06-30", 1.1),
    ("CY2025Q3", "2025-09-30", 1.25), ("CY2025Q4", "2025-12-31", 1.4),
])


def test_language_for_exchange():
    assert _language_for(["Nasdaq"]) == "en"
    assert _language_for(["NYSE"]) == "en"
    assert _language_for(["KRX", "KOSPI"]) == "ko"
    assert _language_for(["KOSDAQ"]) == "ko"


def test_build_trend_margins_and_yoy():
    rows = build_trend({"revenue": REV, "gross_profit": GP, "eps_diluted": EPS}, last_n=4)
    assert len(rows) == 4
    first, last = rows[0], rows[-1]
    assert first.period == "CY2025Q1"
    assert first.revenue == 120.0
    assert first.gross_margin == 50.0          # 60 / 120
    assert first.revenue_yoy_pct == 20.0       # 120 vs 100
    assert first.eps_diluted == 1.0
    assert last.period == "CY2025Q4"
    assert last.revenue_yoy_pct == 30.0        # 169 vs 130
    assert last.gross_margin == 50.0           # 84.5 / 169


def test_build_trend_empty_without_revenue():
    assert build_trend({"gross_profit": GP}, last_n=4) == []


def test_render_markdown_has_sections_and_disclaimer():
    pack = ResearchPack(
        query="ACME",
        language="en",
        profile=CompanyProfile(cik="0000000001", name="Acme Corp", tickers=["ACME"],
                               exchanges=["Nasdaq"], sic_description="Widgets"),
        trend=build_trend({"revenue": REV, "gross_profit": GP, "eps_diluted": EPS}),
        filings=[Filing("8-K", "2026-01-15", "2026-01-15", "0000000001-26-000001",
                        "acme-8k.htm", "https://www.sec.gov/Archives/edgar/data/1/x/acme-8k.htm",
                        items="2.02,9.01")],
        news=[NewsItem("Acme lands big order", "https://news.example/x", "Reuters", "2026-06-20")],
        sources=["SEC EDGAR — https://www.sec.gov/"],
    )
    md = render_markdown(pack)
    assert "# Acme Corp (ACME)" in md
    assert "## Financial trend" in md
    assert "CY2025Q4" in md
    assert "acme-8k.htm" in md                 # filing provenance link present
    assert "Latest earnings release" in md     # 8-K Item 2.02 surfaced
    assert "Results of operations" in md        # decoded item label
    assert "[Acme lands big order](https://news.example/x)" in md   # news, link-only
    assert "not investment advice" in md       # §10 disclaimer
