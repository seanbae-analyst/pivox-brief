"""EDGAR parsers — pure, offline. Fixtures are trimmed captures of the real SEC
responses verified against the live API (RESEARCH_PACK_PLAN.md step 1). No network."""

from engine.edgar import (
    CompanyRef,
    _cik10,
    decode_items,
    financials,  # noqa: F401  (import smoke; exercised live, not here)
    match_company,
    parse_company_tickers,
    parse_concept,
    parse_submissions,
)

# ── company_tickers.json (shape: {"0": {cik_str, ticker, title}, ...}) ────────
TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}

# ── submissions/CIK0000320193.json (trimmed) ─────────────────────────────────
SUBMISSIONS = {
    "cik": 320193,
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
    "sicDescription": "Electronic Computers",
    "filings": {
        "recent": {
            "accessionNumber": ["0001140361-26-025622", "0000320193-26-000060", "0001140361-26-023149"],
            "filingDate": ["2026-06-17", "2026-05-01", "2026-05-28"],
            "reportDate": ["2026-06-15", "2026-03-28", ""],
            "form": ["8-K", "10-Q", "SD"],
            "items": ["2.02,9.01", "", ""],
            "primaryDocument": ["nvda-8k.htm", "aapl-20260328.htm", "ef20073373_sd.htm"],
        }
    },
}

# ── companyconcept revenue (USD): quarters (~90d), a YTD (~180d), an annual (~365d),
# a restatement, and an un-framed most-recent quarter (the NVDA case). ───────────
REVENUE = {
    "label": "Revenues",
    "units": {
        "USD": [
            # annual 10-K (~363d) — excluded by duration
            {"start": "2024-09-29", "end": "2025-09-27", "val": 400e9, "fy": 2025,
             "fp": "FY", "form": "10-K", "frame": "CY2025", "filed": "2025-11-01"},
            # year-to-date 6-month (~181d) — excluded by duration
            {"start": "2025-03-30", "end": "2025-09-27", "val": 194e9, "fy": 2025,
             "fp": "Q3", "form": "10-Q", "frame": None, "filed": "2025-11-01"},
            {"start": "2025-03-30", "end": "2025-06-28", "val": 94036e6, "fy": 2025,
             "fp": "Q3", "form": "10-Q", "frame": "CY2025Q2", "filed": "2025-08-01"},
            {"start": "2025-06-29", "end": "2025-09-27", "val": 100000e6, "fy": 2025,
             "fp": "Q4", "form": "10-Q", "frame": "CY2025Q3", "filed": "2025-11-01"},
            {"start": "2025-09-28", "end": "2025-12-27", "val": 143756e6, "fy": 2026,
             "fp": "Q1", "form": "10-Q", "frame": "CY2025Q4", "filed": "2026-02-01"},
            # earlier restatement of that same quarter — deduped out (kept the later filing)
            {"start": "2025-09-28", "end": "2025-12-27", "val": 143000e6, "fy": 2026,
             "fp": "Q1", "form": "10-Q/A", "frame": None, "filed": "2026-01-15"},
            # most-recent quarter, UN-framed — must survive on duration alone
            {"start": "2025-12-28", "end": "2026-03-28", "val": 111184e6, "fy": 2026,
             "fp": "Q2", "form": "10-Q", "frame": None, "filed": "2026-05-01"},
        ]
    },
}

# ── companyconcept EPS diluted (USD/shares) — flows, so they carry start+end ──
EPS = {
    "units": {
        "USD/shares": [
            {"start": "2024-12-29", "end": "2025-03-29", "val": 1.65, "fy": 2026, "fp": "Q2",
             "form": "10-Q", "frame": "CY2025Q1", "filed": "2025-05-01"},
            {"start": "2025-12-28", "end": "2026-03-28", "val": 1.85, "fy": 2026, "fp": "Q2",
             "form": "10-Q", "frame": "CY2026Q1", "filed": "2026-05-01"},
        ]
    },
}


def test_cik10_normalizes_forms():
    assert _cik10(320193) == "0000320193"
    assert _cik10("320193") == "0000320193"
    assert _cik10("CIK0000320193") == "0000320193"


def test_parse_company_tickers_zero_pads_cik():
    table = parse_company_tickers(TICKERS)
    assert table["AAPL"] == CompanyRef(cik="0000320193", ticker="AAPL", title="Apple Inc.")
    assert table["MSFT"].cik == "0000789019"


def test_match_company_by_ticker():
    table = parse_company_tickers(TICKERS)
    assert match_company(table, "aapl").ticker == "AAPL"


def test_match_company_by_name_substring():
    table = parse_company_tickers(TICKERS)
    assert match_company(table, "microsoft").ticker == "MSFT"


def test_match_company_unknown_returns_none():
    assert match_company(parse_company_tickers(TICKERS), "ZZZZ") is None


def test_parse_submissions_profile_and_form_filter():
    profile, filings = parse_submissions(SUBMISSIONS, forms=("10-Q",), limit=10)
    assert profile.name == "Apple Inc."
    assert profile.cik == "0000320193"
    assert profile.exchanges == ["Nasdaq"]
    # only the 10-Q survives the filter
    assert len(filings) == 1
    f = filings[0]
    assert f.form == "10-Q" and f.report_date == "2026-03-28"
    assert f.url == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000060/aapl-20260328.htm"


def test_parse_submissions_carries_8k_items():
    _, filings = parse_submissions(SUBMISSIONS, forms=("8-K",), limit=10)
    assert len(filings) == 1
    assert filings[0].items == "2.02,9.01"


def test_decode_items():
    assert decode_items("2.02,9.01") == ["Results of operations", "Financial statements & exhibits"]
    assert decode_items("2.02") == ["Results of operations"]
    assert decode_items("9.99") == ["Item 9.99"]   # unknown code passes through
    assert decode_items("") == []


def test_parse_concept_uses_duration_not_frame_and_dedupes():
    pts = parse_concept(REVENUE, n_quarters=4)
    assert len(pts) == 4
    assert [p.end for p in pts] == ["2025-06-28", "2025-09-27", "2025-12-27", "2026-03-28"]
    # the un-framed most-recent quarter survives purely on its ~90d duration (NVDA bug)
    assert pts[-1].frame is None and pts[-1].val == 111184e6
    # restatement of the prior quarter deduped to the later-filed value
    assert pts[2].val == 143756e6
    assert 400e9 not in [p.val for p in pts]   # annual (~363d) excluded
    assert 194e9 not in [p.val for p in pts]   # year-to-date (~181d) excluded


def test_parse_concept_handles_per_share_unit():
    pts = parse_concept(EPS, n_quarters=4)
    assert [p.val for p in pts] == [1.65, 1.85]
