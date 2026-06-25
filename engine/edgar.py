"""SEC EDGAR client — keyless US issuer data (RESEARCH_PACK_PLAN.md step 1).

Official US government disclosure system (https://www.sec.gov). Free programmatic
access under SEC's fair-access policy: a declared ``User-Agent`` (set
``EDGAR_USER_AGENT`` with contact info) and <= 10 requests/second. Three keyless
endpoints back the US research pack:

  ticker -> CIK     www.sec.gov/files/company_tickers.json
  recent filings    data.sec.gov/submissions/CIK##########.json
  XBRL financials   data.sec.gov/api/xbrl/companyconcept/CIK.../us-gaap/<tag>.json

Cleanest US source (DATA_SOURCES.md): a government disclosure system, no
redistribution of third-party text — we keep only derived facts + provenance
links. I/O (``_get``) is deliberately split from parsing (``parse_*``/``match_*``)
so the parsers are pure and unit-tested offline against captured fixtures; nothing
in the test suite touches the network.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date
from typing import Optional

import requests

SEC_WWW = "https://www.sec.gov"
SEC_DATA = "https://data.sec.gov"

# SEC ceiling is 10 req/s; keep a margin. Module-level throttle shared by all _get.
_MIN_INTERVAL = 0.12
_last_request_at = 0.0

# Revenue is tagged differently across issuers/eras — try in order, take the first
# that returns data. The rest are single-tag in current us-gaap.
REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
GROSS_PROFIT_CONCEPTS = ("GrossProfit",)
OPERATING_INCOME_CONCEPTS = ("OperatingIncomeLoss",)
NET_INCOME_CONCEPTS = ("NetIncomeLoss",)
EPS_DILUTED_CONCEPTS = ("EarningsPerShareDiluted",)

# ── extended research-pack concepts (valuation / health / capital return) ─────
# Instant (point-in-time, balance-sheet & cover) concepts — read the LATEST value.
SHARES_CONCEPTS = ("EntityCommonStockSharesOutstanding",)  # dei namespace, unit "shares"
EQUITY_CONCEPTS = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
)
CASH_CONCEPTS = (
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
)
DEBT_TOTAL_CONCEPTS = ("LongTermDebt",)                # total (incl. current portion) where filed as one tag
DEBT_NONCURRENT_CONCEPTS = ("LongTermDebtNoncurrent",)
DEBT_CURRENT_CONCEPTS = ("LongTermDebtCurrent", "DebtCurrent")
CURRENT_ASSETS_CONCEPTS = ("AssetsCurrent",)
CURRENT_LIABS_CONCEPTS = ("LiabilitiesCurrent",)

# Flow concepts filed on a fiscal-YTD basis (cash-flow statement) — read the latest
# ANNUAL (~365-day) value, since interim 10-Q figures are cumulative, not discrete quarters.
OCF_CONCEPTS = (
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
)
CAPEX_CONCEPTS = ("PaymentsToAcquirePropertyPlantAndEquipment",)
DIVIDENDS_CONCEPTS = ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends")
BUYBACKS_CONCEPTS = ("PaymentsForRepurchaseOfCommonStock",)
DA_CONCEPTS = (
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
)

# Form 8-K item codes -> human labels (common subset of SEC's item index). 2.02 is
# the earnings release ("Results of Operations and Financial Condition").
EIGHT_K_ITEMS = {
    "1.01": "Material agreement",
    "1.02": "Termination of material agreement",
    "2.01": "Completed acquisition/disposition",
    "2.02": "Results of operations",
    "2.03": "Material financial obligation",
    "2.05": "Costs from exit/disposal",
    "3.01": "Delisting / listing-rule notice",
    "3.02": "Unregistered equity sale",
    "4.01": "Auditor change",
    "5.02": "Officer / director change",
    "5.03": "Bylaw / charter amendment",
    "5.07": "Shareholder vote results",
    "7.01": "Reg FD disclosure",
    "8.01": "Other events",
    "9.01": "Financial statements & exhibits",
}
EARNINGS_ITEM = "2.02"


def decode_items(items: str) -> list[str]:
    """"2.02,9.01" -> ["Results of operations", "Financial statements & exhibits"]."""
    labels = []
    for code in (c.strip() for c in (items or "").split(",")):
        if code:
            labels.append(EIGHT_K_ITEMS.get(code, f"Item {code}"))
    return labels


# ── data shapes ──────────────────────────────────────────────────────────────
@dataclass
class CompanyRef:
    cik: str        # 10-digit zero-padded, e.g. "0000320193"
    ticker: str
    title: str


@dataclass
class CompanyProfile:
    cik: str
    name: str
    tickers: list[str]
    exchanges: list[str]
    sic_description: str


@dataclass
class Filing:
    form: str
    filing_date: str
    report_date: str
    accession: str
    primary_document: str
    url: str          # direct link to the primary document (provenance)
    items: str = ""   # 8-K item codes, e.g. "2.02,9.01" (empty for other forms)


@dataclass
class FactPoint:
    end: str
    val: float
    fy: Optional[int]
    fp: Optional[str]
    form: str
    frame: Optional[str]
    start: Optional[str] = None


@dataclass
class FinancialSeries:
    concept: str             # the us-gaap tag that resolved
    points: list[FactPoint]


# ── HTTP (rate-limited, identified) ──────────────────────────────────────────
def _user_agent() -> str:
    """SEC fair-access requires a declared identity. Set EDGAR_USER_AGENT to your
    own contact (e.g. "yourname you@example.com") in .env — see DATA_SOURCES.md."""
    return os.environ.get("EDGAR_USER_AGENT") or "pivox-brief/0.1 (research tool; set EDGAR_USER_AGENT)"


def _throttle() -> None:
    global _last_request_at
    wait = _MIN_INTERVAL - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _get(url: str) -> dict:
    _throttle()
    resp = requests.get(
        url,
        headers={"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_text(url: str) -> str:
    """Fetch a filing document (HTML/text) under the same fair-access policy as ``_get``
    (declared User-Agent, rate-limited). Returns the raw response body — ``engine.filings``
    strips and slices it for the qualitative read (MD&A / risk factors, Layer 2). Only
    official EDGAR documents are fetched; derived facts only, never republished (§1)."""
    _throttle()
    resp = requests.get(
        url,
        headers={"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text


def _cik10(cik: int | str) -> str:
    """Normalize 320193 / "320193" / "CIK0000320193" -> "0000320193"."""
    digits = str(cik).upper().replace("CIK", "").strip()
    return str(int(digits)).zfill(10)


# ── pure parsers ─────────────────────────────────────────────────────────────
def parse_company_tickers(data: dict) -> dict[str, CompanyRef]:
    """{"0": {cik_str, ticker, title}, ...} -> {TICKER: CompanyRef}."""
    out: dict[str, CompanyRef] = {}
    for row in data.values():
        ref = CompanyRef(
            cik=str(row["cik_str"]).zfill(10),
            ticker=str(row["ticker"]).upper(),
            title=str(row["title"]),
        )
        out[ref.ticker] = ref
    return out


def match_company(table: dict[str, CompanyRef], query: str) -> Optional[CompanyRef]:
    """Exact ticker match first, then case-insensitive name substring."""
    q = query.strip().upper()
    if not q:
        return None
    if q in table:
        return table[q]
    for ref in table.values():
        if q in ref.title.upper():
            return ref
    return None


def parse_submissions(
    data: dict,
    forms: Optional[tuple[str, ...]] = None,
    limit: int = 10,
) -> tuple[CompanyProfile, list[Filing]]:
    """submissions JSON -> (profile, filings). ``forms`` filters by exact form type."""
    profile = CompanyProfile(
        cik=_cik10(data["cik"]),
        name=data.get("name", ""),
        tickers=list(data.get("tickers", [])),
        exchanges=list(data.get("exchanges", [])),
        sic_description=data.get("sicDescription", ""),
    )
    recent = data.get("filings", {}).get("recent", {})
    items_arr = recent.get("items", [])
    cik_int = int(profile.cik)
    filings: list[Filing] = []
    for i in range(len(recent.get("form", []))):
        form = recent["form"][i]
        if forms and form not in forms:
            continue
        accn = recent["accessionNumber"][i]
        doc = recent["primaryDocument"][i]
        folder = accn.replace("-", "")
        base = f"{SEC_WWW}/Archives/edgar/data/{cik_int}/{folder}"
        url = f"{base}/{doc}" if doc else f"{base}/"
        filings.append(
            Filing(
                form=form,
                filing_date=recent["filingDate"][i],
                report_date=recent["reportDate"][i],
                accession=accn,
                primary_document=doc,
                url=url,
                items=items_arr[i] if i < len(items_arr) else "",
            )
        )
        if len(filings) >= limit:
            break
    return profile, filings


def _pick_unit(units: dict) -> list[dict]:
    """Most XBRL financials are USD; per-share figures (EPS) are USD/shares."""
    for key in ("USD", "USD/shares"):
        if key in units:
            return units[key]
    return next(iter(units.values()), [])


def parse_concept(data: dict, n_quarters: int = 4) -> list[FactPoint]:
    """Last ``n_quarters`` quarterly data points from a companyconcept response.

    A quarter is identified by DURATION — a ~90-day ``start``->``end`` span. That is
    the reliable signal across issuers: SEC's calendar ``frame`` tags are sparse and
    sometimes stale (companies with non-calendar fiscal years, e.g. NVDA, leave
    recent quarters un-framed), so frame is kept only as a display hint. Duration
    naturally excludes year-to-date (6/9-month) and annual (10-K, ~365-day) rows;
    restatements that share a period end are deduped, keeping the most recently
    filed. ``companyconcept`` returns one consolidated value per period (no segment
    breakdowns), so dedup-by-end is safe.
    """
    rows = _pick_unit(data.get("units", {}))

    quarterly = []
    for r in rows:
        start, end = r.get("start"), r.get("end")
        if not (start and end):
            continue
        try:
            span = (date.fromisoformat(end) - date.fromisoformat(start)).days
        except ValueError:
            continue
        if 80 <= span <= 100:
            quarterly.append(r)

    # Dedupe by period end, keeping the most-recently-filed (restatement-safe).
    by_end: dict[str, dict] = {}
    for r in sorted(quarterly, key=lambda x: str(x.get("filed", ""))):
        by_end[r["end"]] = r

    points = [
        FactPoint(
            end=r["end"],
            val=float(r["val"]),
            fy=r.get("fy"),
            fp=r.get("fp"),
            form=str(r.get("form", "")),
            frame=r.get("frame"),
            start=r.get("start"),
        )
        for r in sorted(by_end.values(), key=lambda x: x["end"])
    ]
    return points[-n_quarters:]


def _to_points(rows: list[dict]) -> list[FactPoint]:
    """Dedupe rows by period end (keep the most-recently-filed = restatement-safe),
    return FactPoints sorted by end. Shared by the instant and annual parsers."""
    by_end: dict[str, dict] = {}
    for r in sorted(rows, key=lambda x: str(x.get("filed", ""))):
        by_end[r["end"]] = r
    return [
        FactPoint(
            end=r["end"],
            val=float(r["val"]),
            fy=r.get("fy"),
            fp=r.get("fp"),
            form=str(r.get("form", "")),
            frame=r.get("frame"),
            start=r.get("start"),
        )
        for r in sorted(by_end.values(), key=lambda x: x["end"])
    ]


def parse_instant(data: dict, n: int = 1) -> list[FactPoint]:
    """Latest ``n`` point-in-time (balance-sheet / cover) values from a companyconcept
    response. Instant facts carry an ``end`` with no distinct duration; durations are
    excluded so a single instant tag isn't polluted by any flow rows under the same name."""
    rows = []
    for r in _pick_unit(data.get("units", {})):
        end, start = r.get("end"), r.get("start")
        if not end:
            continue
        if start and start != end:
            try:
                if (date.fromisoformat(end) - date.fromisoformat(start)).days > 5:
                    continue  # a real duration, not an instant
            except ValueError:
                continue
        rows.append(r)
    return _to_points(rows)[-n:]


def parse_annual(data: dict, n: int = 1) -> list[FactPoint]:
    """Latest ``n`` ANNUAL (~365-day duration) values. The robust basis for cash-flow
    items (OCF, capex, dividends, buybacks), whose interim 10-Q figures are fiscal-YTD
    cumulative rather than discrete quarters — so summing quarters would double-count."""
    rows = []
    for r in _pick_unit(data.get("units", {})):
        start, end = r.get("start"), r.get("end")
        if not (start and end):
            continue
        try:
            span = (date.fromisoformat(end) - date.fromisoformat(start)).days
        except ValueError:
            continue
        if 350 <= span <= 380:
            rows.append(r)
    return _to_points(rows)[-n:]


# ── I/O wrappers (fetch + parse) ─────────────────────────────────────────────
_TICKER_TABLE: Optional[dict] = None


def _ticker_table() -> dict:
    """Process-lifetime cache of the ticker→CIK table (a few hundred KB). Re-downloading
    it per call was a real cost on the serverless search path and when resolving a watchlist."""
    global _TICKER_TABLE
    if _TICKER_TABLE is None:
        _TICKER_TABLE = parse_company_tickers(_get(f"{SEC_WWW}/files/company_tickers.json"))
    return _TICKER_TABLE


def resolve_ticker(query: str) -> Optional[CompanyRef]:
    """Resolve a ticker (exact) or company name (substring) to a CompanyRef."""
    return match_company(_ticker_table(), query)


def first_series(
    cik: int | str,
    concepts: tuple[str, ...],
    n_quarters: int = 4,
    *,
    namespace: str = "us-gaap",
    kind: str = "duration",
) -> Optional[FinancialSeries]:
    """The FIRST concept in preference order that returns data. Use this (not ``best_series``)
    when the candidates are NOT synonyms — e.g. cash, where the preferred tag is unrestricted
    cash and the fallback also includes restricted cash (different meanings)."""
    for concept in concepts:
        points = concept_points(cik, concept, n_quarters, namespace=namespace, kind=kind)
        if points:
            return FinancialSeries(concept=concept, points=points)
    return None


def company_filings(
    cik: int | str,
    forms: tuple[str, ...] = ("8-K", "10-Q", "10-K"),
    limit: int = 10,
) -> tuple[CompanyProfile, list[Filing]]:
    data = _get(f"{SEC_DATA}/submissions/CIK{_cik10(cik)}.json")
    return parse_submissions(data, forms=forms, limit=limit)


def concept_points(
    cik: int | str,
    concept: str,
    n_quarters: int = 4,
    *,
    namespace: str = "us-gaap",
    kind: str = "duration",
) -> list[FactPoint]:
    """One concept's recent points. [] if the tag isn't filed (404).

    ``kind``: "duration" (discrete quarters, ``parse_concept``) | "instant" (balance-sheet,
    ``parse_instant``) | "annual" (~365-day, ``parse_annual``).
    ``namespace``: "us-gaap" (default) | "dei" (cover-page facts, e.g. shares outstanding).
    """
    url = f"{SEC_DATA}/api/xbrl/companyconcept/CIK{_cik10(cik)}/{namespace}/{concept}.json"
    try:
        data = _get(url)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return []
        raise
    if kind == "instant":
        return parse_instant(data, n_quarters)
    if kind == "annual":
        return parse_annual(data, n_quarters)
    return parse_concept(data, n_quarters)


def best_series(
    cik: int | str,
    concepts: tuple[str, ...],
    n_quarters: int = 4,
    *,
    namespace: str = "us-gaap",
    kind: str = "duration",
) -> Optional[FinancialSeries]:
    """The candidate concept with the MOST RECENT data.

    Not merely the first that returns rows — issuers migrate tags and leave the old
    one frozen (e.g. NVDA's ``RevenueFromContractWithCustomerExcludingAssessedTax``
    stops in 2020; current revenue is under ``Revenues``). Picking by latest period
    end follows the live tag.
    """
    best: Optional[FinancialSeries] = None
    best_end = ""
    for concept in concepts:
        points = concept_points(cik, concept, n_quarters, namespace=namespace, kind=kind)
        if points and points[-1].end > best_end:
            best = FinancialSeries(concept=concept, points=points)
            best_end = points[-1].end
    return best


def financials(cik: int | str, n_quarters: int = 4) -> dict[str, FinancialSeries]:
    """The standard research-pack financial series (revenue/margins inputs/EPS).

    Returns only the series that resolved — callers derive margins (gross/operating/
    net = the income line / revenue) and render whatever is present.
    """
    wanted = {
        "revenue": REVENUE_CONCEPTS,
        "gross_profit": GROSS_PROFIT_CONCEPTS,
        "operating_income": OPERATING_INCOME_CONCEPTS,
        "net_income": NET_INCOME_CONCEPTS,
        "eps_diluted": EPS_DILUTED_CONCEPTS,
    }
    out: dict[str, FinancialSeries] = {}
    for key, concepts in wanted.items():
        series = best_series(cik, concepts, n_quarters)
        if series:
            out[key] = series
    return out


def extended_facts(cik: int | str, n_recent: int = 6) -> dict[str, FinancialSeries]:
    """Balance-sheet (instant) + annual cash-flow series behind the valuation / health /
    capital-return factors. Each key is present only if its XBRL tag resolved, so callers
    render whatever is available (same philosophy as ``financials``). Debt is exposed as
    up to three tags — callers prefer ``debt_total`` else ``debt_noncurrent`` + ``debt_current``.
    """
    out: dict[str, FinancialSeries] = {}

    # Instant (point-in-time) — latest balance-sheet & cover-page values.
    instant = {
        "shares": (SHARES_CONCEPTS, "dei"),
        "equity": (EQUITY_CONCEPTS, "us-gaap"),
        "cash": (CASH_CONCEPTS, "us-gaap"),
        "current_assets": (CURRENT_ASSETS_CONCEPTS, "us-gaap"),
        "current_liabs": (CURRENT_LIABS_CONCEPTS, "us-gaap"),
        "debt_total": (DEBT_TOTAL_CONCEPTS, "us-gaap"),
        "debt_noncurrent": (DEBT_NONCURRENT_CONCEPTS, "us-gaap"),
        "debt_current": (DEBT_CURRENT_CONCEPTS, "us-gaap"),
    }
    # Balance-sheet tags are always currently filed, and several candidate lists are NOT
    # synonyms (cash: unrestricted vs incl-restricted; equity: vs incl-noncontrolling), so the
    # FIRST preferred tag that resolves is the right pick — not best_series's "latest end".
    for key, (concepts, ns) in instant.items():
        series = first_series(cik, concepts, n_recent, namespace=ns, kind="instant")
        if series:
            out[key] = series

    # Annual (~365d) — robust basis for fiscal-YTD cash-flow items.
    annual = {
        "ocf": OCF_CONCEPTS,
        "capex": CAPEX_CONCEPTS,
        "dividends": DIVIDENDS_CONCEPTS,
        "buybacks": BUYBACKS_CONCEPTS,
        "da": DA_CONCEPTS,
        "revenue_annual": REVENUE_CONCEPTS,
        "operating_income_annual": OPERATING_INCOME_CONCEPTS,
        "net_income_annual": NET_INCOME_CONCEPTS,
    }
    for key, concepts in annual.items():
        series = best_series(cik, concepts, n_recent, kind="annual")
        if series:
            out[key] = series
    return out
