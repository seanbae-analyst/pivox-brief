"""Research pack assembler (RESEARCH_PACK_PLAN.md step 4).

Search a ticker / company name -> a one-page brief of price-relevant factors, in
the right language (US stock -> English; KR stock -> Korean, once engine/dart.py
lands). This module assembles the US/EDGAR pack and renders it to Markdown.

Design: the pure parts — deriving the financial trend (margins, YoY) from EDGAR
series and rendering Markdown — are split from the I/O entry point ``build_us_pack``
so they unit-test offline. A pack is a *research starting point*, not investment
advice (§10): every number carries its source, and the renderer ends on the
disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from engine import edgar
from engine.edgar import CompanyProfile, Filing, FinancialSeries

# Earnings-relevant forms, in the order a reader scans them.
EARNINGS_FORMS = ("8-K", "10-Q", "10-K")


@dataclass
class QuarterRow:
    period: str                         # frame label e.g. "CY2026Q1", else the end date
    end: str
    revenue: Optional[float] = None
    gross_margin: Optional[float] = None      # percent
    operating_margin: Optional[float] = None  # percent
    net_margin: Optional[float] = None        # percent
    eps_diluted: Optional[float] = None
    revenue_yoy_pct: Optional[float] = None


@dataclass
class ResearchPack:
    query: str
    language: str                       # "en" (US) | "ko" (KR, later)
    profile: CompanyProfile
    trend: list[QuarterRow] = field(default_factory=list)
    filings: list[Filing] = field(default_factory=list)
    price: Optional[object] = None      # engine.prices.LatestClose | None (demo-labeled)
    news: list = field(default_factory=list)   # engine.news.NewsItem (link-only, §4)
    sources: list[str] = field(default_factory=list)


# ── pure assembly ────────────────────────────────────────────────────────────
def _margin(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
    if numer is None or not denom:
        return None
    return round(numer / denom * 100.0, 1)


def _calendar_quarter(start: Optional[str], end: str) -> str:
    """SEC-style calendar-quarter label from the period midpoint — matches the
    ``frame`` convention (a ~3-month period is labeled by the quarter it mostly
    covers, e.g. a period ending late July sits in Q2, not Q3)."""
    try:
        e = date.fromisoformat(end)
        s = date.fromisoformat(start) if start else e
    except (TypeError, ValueError):
        return end
    mid = s + (e - s) / 2
    return f"CY{mid.year}Q{(mid.month - 1) // 3 + 1}"


def _period_label(point) -> str:
    """Calendar quarter, comparable across issuers. The issuer's own fiscal ``fp``/
    ``fy`` is deliberately NOT used — under restatement dedup a quarter's most-recent
    instance can be a comparative carrying the *filing's* fiscal year, which mislabels
    and collides. SEC's ``frame`` (when present) or the midpoint derivation is stable."""
    return point.frame or _calendar_quarter(getattr(point, "start", None), point.end)


def _revenue_yoy(point, rev_points) -> Optional[float]:
    """YoY vs the revenue quarter ~365 days earlier, matched by period-end date.

    Frame-independent (frames are unreliable, see engine.edgar.parse_concept) and
    tolerant of fiscal-quarter-end drift (52/53-week calendars shift the date a few
    days year to year). +-29 days can't collide with an adjacent quarter (~90 days off).
    """
    target = date.fromisoformat(point.end) - timedelta(days=365)
    best, best_diff = None, 30
    for q in rev_points:
        if q.end >= point.end:
            continue
        diff = abs((date.fromisoformat(q.end) - target).days)
        if diff < best_diff:
            best, best_diff = q, diff
    if best and best.val:
        return round((point.val / best.val - 1.0) * 100.0, 1)
    return None


def build_trend(fin: dict[str, FinancialSeries], last_n: int = 4) -> list[QuarterRow]:
    """Derive the quarterly trend (margins + revenue YoY) from EDGAR series.

    Margins are matched to revenue by period end; YoY matches the quarter ~1 year
    earlier by end date, so callers should fetch >= last_n + 4 quarters to populate it.
    """
    if "revenue" not in fin:
        return []

    rev_points = sorted(fin["revenue"].points, key=lambda p: p.end)
    by_end = lambda key: {p.end: p.val for p in fin[key].points} if key in fin else {}
    gp, oi, ni, eps = (by_end(k) for k in ("gross_profit", "operating_income", "net_income", "eps_diluted"))

    rows: list[QuarterRow] = []
    for p in rev_points[-last_n:]:
        rows.append(
            QuarterRow(
                period=_period_label(p),
                end=p.end,
                revenue=p.val,
                gross_margin=_margin(gp.get(p.end), p.val),
                operating_margin=_margin(oi.get(p.end), p.val),
                net_margin=_margin(ni.get(p.end), p.val),
                eps_diluted=eps.get(p.end),
                revenue_yoy_pct=_revenue_yoy(p, rev_points),
            )
        )
    return rows


def _latest(filings: list[Filing], predicate) -> Optional[Filing]:
    """First match — submissions are most-recent-first, so this is the latest."""
    return next((f for f in filings if predicate(f)), None)


def earnings_read(filings: list[Filing]) -> dict[str, Optional[Filing]]:
    """The three filings a reader reaches for: the latest earnings release (8-K
    carrying Item 2.02), the latest 10-Q (MD&A + financials), and the latest 10-K
    (whose Item 1A is the risk-factors section)."""
    return {
        "earnings_8k": _latest(filings, lambda f: f.form == "8-K" and edgar.EARNINGS_ITEM in (f.items or "")),
        "latest_10q": _latest(filings, lambda f: f.form == "10-Q"),
        "latest_10k": _latest(filings, lambda f: f.form == "10-K"),
    }


def _language_for(exchanges: list[str]) -> str:
    """US exchanges -> English. KR exchanges (KRX/KOSPI/KOSDAQ) -> Korean (DART path)."""
    blob = " ".join(exchanges).upper()
    if any(k in blob for k in ("KRX", "KOSPI", "KOSDAQ", "KONEX")):
        return "ko"
    return "en"


# ── I/O entry point ──────────────────────────────────────────────────────────
def build_us_pack(query: str, n_quarters: int = 8, with_price: bool = True) -> Optional[ResearchPack]:
    """Resolve a US ticker/name via EDGAR and assemble its research pack.

    Returns None if the query doesn't resolve in EDGAR — the caller can then route
    to the KR/DART path (engine/dart.py, pending the DART key).
    """
    ref = edgar.resolve_ticker(query)
    if ref is None:
        return None

    profile, filings = edgar.company_filings(ref.cik, forms=EARNINGS_FORMS, limit=8)
    fin = edgar.financials(ref.cik, n_quarters=n_quarters)
    trend = build_trend(fin, last_n=4)

    price = None
    if with_price:
        try:
            from engine.prices import latest_close

            price = latest_close(ref.ticker)
        except Exception:
            price = None  # gray/optional source — never block the pack on it

    from engine.news import load_news

    sources = [
        f"SEC EDGAR — submissions: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={profile.cik}&type=&dateb=&owner=include&count=40",
        f"SEC EDGAR XBRL company facts: https://data.sec.gov/api/xbrl/companyfacts/CIK{profile.cik}.json",
    ]
    return ResearchPack(
        query=query,
        language=_language_for(profile.exchanges),
        profile=profile,
        trend=trend,
        filings=filings,
        price=price,
        news=load_news(ref.ticker),
        sources=sources,
    )


# ── rendering ────────────────────────────────────────────────────────────────
def _fmt_usd(v: Optional[float]) -> str:
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.0f}"


def _fmt_pct(v: Optional[float], sign: bool = False) -> str:
    if v is None:
        return "—"
    return (f"{v:+.1f}%" if sign else f"{v:.1f}%")


DISCLAIMER = (
    "*Research starting point compiled from public SEC filings — descriptive only, "
    "**not investment advice** (§10). Verify against the linked primary sources before acting.*"
)


def render_markdown(pack: ResearchPack) -> str:
    """One-page Markdown brief (English). KR rendering follows with the DART path."""
    p = pack.profile
    ticker = p.tickers[0] if p.tickers else pack.query.upper()
    lines: list[str] = []

    # Header + snapshot
    lines.append(f"# {p.name} ({ticker})")
    snap = [f"**Exchange:** {', '.join(p.exchanges) or '—'}", f"**Industry:** {p.sic_description or '—'}", f"**CIK:** {p.cik}"]
    if pack.price is not None:
        snap.append(f"**Last close:** ${pack.price.close} ({pack.price.date}) ⟨demo data⟩")
    lines.append("  •  ".join(snap))
    lines.append("")

    # Financial trend
    lines.append("## Financial trend (quarterly, SEC XBRL)")
    if pack.trend:
        lines.append("| Period | Revenue | Rev YoY | Gross % | Oper % | Net % | Diluted EPS |")
        lines.append("|---|--:|--:|--:|--:|--:|--:|")
        for r in pack.trend:
            lines.append(
                f"| {r.period} | {_fmt_usd(r.revenue)} | {_fmt_pct(r.revenue_yoy_pct, sign=True)} | "
                f"{_fmt_pct(r.gross_margin)} | {_fmt_pct(r.operating_margin)} | {_fmt_pct(r.net_margin)} | "
                f"{('$%.2f' % r.eps_diluted) if r.eps_diluted is not None else '—'} |"
            )
    else:
        lines.append("_No standardized XBRL financials available for this issuer._")
    lines.append("")

    # Earnings read — the filings a reader reaches for first
    lines.append("## Earnings read")
    read = earnings_read(pack.filings)
    if read["earnings_8k"]:
        f = read["earnings_8k"]
        lines.append(f"- **Latest earnings release** — 8-K, Results of operations · filed {f.filing_date} — [{f.primary_document or 'filing'}]({f.url})")
    if read["latest_10q"]:
        f = read["latest_10q"]
        lines.append(f"- **Latest 10-Q** — MD&A + financials · filed {f.filing_date} — [{f.primary_document or 'filing'}]({f.url})")
    if read["latest_10k"]:
        f = read["latest_10k"]
        lines.append(f"- **Risk factors** — Item 1A, latest 10-K · filed {f.filing_date} — [{f.primary_document or 'filing'}]({f.url})")
    if not any(read.values()):
        lines.append("_No earnings 8-K / 10-Q / 10-K on file._")
    lines.append("")

    # Full recent-filing list, each labeled by what it covers (8-K item decode)
    lines.append("### Recent filings")
    if pack.filings:
        for f in pack.filings:
            extras = []
            if f.report_date:
                extras.append(f"period {f.report_date}")
            labels = edgar.decode_items(f.items)
            if labels:
                extras.append("; ".join(labels))
            tail = f" — {' · '.join(extras)}" if extras else ""
            lines.append(f"- **{f.form}** · filed {f.filing_date}{tail} — [{f.primary_document or 'filing'}]({f.url})")
    else:
        lines.append("_No recent filings on file._")
    lines.append("")

    # News & catalysts — headline + link only (§4); no article text reproduced
    lines.append("## News & catalysts")
    if pack.news:
        for n in pack.news:
            meta = " · ".join(x for x in (n.source, n.date) if x)
            lines.append(f"- [{n.headline}]({n.url})" + (f" — {meta}" if meta else ""))
        lines.append("")
        lines.append("_Headlines + links only (DATA_SOURCES.md §4); no article text reproduced._")
    else:
        lines.append("_No cached headlines — populate `data/news/<TICKER>.json` (headline + link only, §4)._")
    lines.append("")

    # Sources + disclaimer
    lines.append("## Sources")
    for s in pack.sources:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("---")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
