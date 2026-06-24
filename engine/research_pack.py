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
    quant: Optional[dict] = None        # engine.factors.compute_quant block (Layer 1)
    qualitative: Optional[dict] = None  # engine.research_schema.QualitativeBlock dump (Layer 2)
    ownership: Optional[dict] = None    # engine.ownership.ownership_block (insider Form 4 + 13D/G)
    quality_flags: Optional[list] = None  # engine.quality_flags (earnings-quality observations)
    risk_delta: Optional[dict] = None   # engine.risk_delta (10-K Item 1A YoY change)


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
def build_us_pack(query: str, n_quarters: int = 8, with_price: bool = True,
                  with_ownership: bool = True, with_risk_delta: bool = True) -> Optional[ResearchPack]:
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
    ext = edgar.extended_facts(ref.cik)

    # One demo-price fetch (technicals carries the last close) feeds both the snapshot
    # and the quant price block — never block the pack if the gray source is down (§5).
    tech = None
    price = None
    if with_price:
        try:
            from engine.prices import LatestClose, technicals

            tech = technicals(ref.ticker)
            if tech is not None:
                price = LatestClose(ref.ticker, tech.as_of, tech.last_close)
        except Exception:
            tech = price = None

    from engine.factors import compute_quant

    quant = compute_quant(fin, ext, price=(tech.last_close if tech else None), technicals=tech)

    ownership = None
    if with_ownership:
        try:
            from engine.ownership import ownership_block

            ownership = ownership_block(ref.cik)
        except Exception:
            ownership = None  # never block the pack on the ownership fetch

    # Refined signal (STRATEGY.md wave 1): earnings-quality flags (cheap, from XBRL we have)
    # + the year-over-year risk-factor delta (fetches 2 10-Ks — gated for latency-sensitive callers).
    from engine.quality_flags import quality_flags as _quality_flags

    quality = _quality_flags(trend, ext)

    risk_delta_block = None
    if with_risk_delta:
        try:
            from engine.risk_delta import risk_delta as _risk_delta

            risk_delta_block = _risk_delta(ref.cik)
        except Exception:
            risk_delta_block = None

    from engine.news import load_news
    from engine.qualitative import load_qualitative

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
        quant=quant,
        qualitative=load_qualitative(ref.ticker),
        ownership=ownership,
        quality_flags=quality,
        risk_delta=risk_delta_block,
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

    # Valuation & quality — Layer-1 quant factors (None-pruned per line)
    q = pack.quant or {}
    v, prof, h, cap, pr = (q.get("valuation") or {}, q.get("profitability") or {},
                           q.get("health") or {}, q.get("capital_return") or {}, q.get("price") or {})
    if any([v, prof, h, pr]):
        def _n(x, suf="", money=False):
            if x is None:
                return "—"
            return _fmt_usd(x) if money else f"{x}{suf}"

        lines.append("## Valuation & quality")
        lines.append(
            f"- **Market cap:** {_n(v.get('market_cap'), money=True)}  •  **P/E (TTM):** {_n(v.get('pe_ttm'), 'x')}  •  "
            f"**P/S:** {_n(v.get('ps_ttm'), 'x')}  •  **P/B:** {_n(v.get('pb'), 'x')}  •  **EV/EBITDA:** {_n(v.get('ev_ebitda'), 'x')}"
        )
        lines.append(
            f"- **FCF yield:** {_n(v.get('fcf_yield_pct'), '%')}  •  **Div yield:** {_n(v.get('dividend_yield_pct'), '%')}  •  "
            f"**Buyback yield:** {_n(v.get('buyback_yield_pct'), '%')}  •  **ROE:** {_n(prof.get('roe_pct'), '%')}"
        )
        lines.append(
            f"- **Margins (TTM):** gross {_n(prof.get('gross_margin_ttm_pct'), '%')} · oper {_n(prof.get('operating_margin_ttm_pct'), '%')} · "
            f"net {_n(prof.get('net_margin_ttm_pct'), '%')} · FCF {_n(prof.get('fcf_margin_pct'), '%')}"
        )
        lines.append(
            f"- **Balance sheet:** net debt {_n(h.get('net_debt'), money=True)} · D/E {_n(h.get('debt_to_equity'))} · "
            f"current ratio {_n(h.get('current_ratio'))} · shares YoY {_n(cap.get('shares_yoy_pct'), '%')}"
        )
        if pr:
            lines.append(
                f"- **Price ⟨demo⟩:** ${_n(pr.get('last_close'))} ({pr.get('as_of')}) · 1M {_n(pr.get('ret_1m_pct'), '%')} · "
                f"YTD {_n(pr.get('ret_ytd_pct'), '%')} · 1Y {_n(pr.get('ret_1y_pct'), '%')} · "
                f"52w ${_n(pr.get('low_52w'))}–${_n(pr.get('high_52w'))} ({_n(pr.get('pct_from_52w_high'), '%')} from high) · "
                f"MA50 ${_n(pr.get('ma50'))} / MA200 ${_n(pr.get('ma200'))}"
            )
        lines.append("")

    # Quality flags — refined earnings-quality / trajectory observations (descriptive)
    if pack.quality_flags:
        lines.append("## Quality flags")
        for f in pack.quality_flags:
            lines.append(f"- {f['observation']}")
        lines.append("")
        lines.append("_Descriptive observations derived from XBRL — not a verdict (§10)._")
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

    # Signal read — Layer-2 qualitative (filings-derived, controlled vocab + confidence)
    qb = pack.qualitative or {}
    if qb and (qb.get("themes") or qb.get("guidance") or qb.get("risk_factors")):
        lines.append("## Signal read (qualitative)")
        g = qb.get("guidance")
        if g:
            det = f" — {g['detail']}" if g.get("detail") else ""
            lines.append(f"- **Guidance:** {g['direction']}{det}  ⟨conf {g.get('confidence', '?')}⟩")
        t = qb.get("tone")
        if t:
            lines.append(f"- **Management tone:** {t['label']}  ⟨conf {t.get('confidence', '?')}⟩")
        for th in qb.get("themes", []):
            arrow = {"positive": "▲", "negative": "▼", "neutral": "•"}.get(th.get("direction"), "•")
            lines.append(f"- {arrow} **{th['theme']}** ({th['direction']}) — {th['evidence']}  ⟨conf {th.get('confidence', '?')}⟩")
        rfs = qb.get("risk_factors", [])
        if rfs:
            lines.append("")
            lines.append("**Key risk factors (10-K Item 1A):**")
            for r in rfs:
                lines.append(f"- {r['summary']}")
        lines.append("")
        lines.append("_Themes mapped to a fixed vocabulary; paraphrased from official filings (no verbatim text, §1)._")
        lines.append("")

    # Risk-factor delta — what changed in 10-K Item 1A year over year
    rd = pack.risk_delta
    if rd and (rd.get("added") or rd.get("removed")):
        lines.append("## Risk-factor delta (10-K Item 1A, YoY)")
        lines.append(f"_Latest 10-K {rd['current_filing']['filed']} ({rd['current_count']} risks) "
                     f"vs prior {rd['prior_filing']['filed']} ({rd['prior_count']})._")
        if rd.get("added"):
            lines.append("")
            lines.append(f"**Added this year ({len(rd['added'])}):**")
            for a in rd["added"]:
                lines.append(f"- ▲ {a}")
        if rd.get("removed"):
            lines.append("")
            lines.append(f"**Removed this year ({len(rd['removed'])}):**")
            for r in rd["removed"]:
                lines.append(f"- ▽ {r}")
        lines.append("")

    # Insider & ownership activity — Form 4 (P/S flagged) + 13D/G links
    own = pack.ownership or {}
    itx, lhf = own.get("insider_transactions", []), own.get("large_holder_filings", [])
    pat = own.get("insider_pattern")
    if itx or lhf:
        lines.append("## Insider & ownership activity")
        if pat and pat.get("observation"):
            lines.append(f"_{pat['observation']}_")
            lines.append("")
        for t in itx:
            sh = f"{t['shares']:,.0f}" if t.get("shares") is not None else "—"
            val = f" (~{_fmt_usd(t['value'])})" if t.get("value") is not None else ""
            flag = "★ " if t.get("discretionary") else ""
            lines.append(
                f"- {flag}**{t['owner']}** ({t['relationship']}) — {t['code_label']} "
                f"{t.get('acquired_disposed', '?')} {sh} sh{val} · {t.get('date') or '—'}"
            )
        if lhf:
            links = ", ".join(f"[{f['form']} {f['filed']}]({f['url']})" for f in lhf[:4])
            lines.append(f"- **Large-holder filings (>5%):** {links}")
        lines.append("")
        lines.append("_★ = discretionary open-market trade (P/S); others are grants/tax/option/gift._")
        lines.append("")

    # Coverage manifest — what this pack sees and (honestly) what it can't
    cov = coverage_manifest(pack)
    lines.append("## Coverage")
    lines.append("**✅ Covered:** " + "; ".join(cov["covered"]) if cov["covered"] else "**✅ Covered:** —")
    lines.append("**🟡 Partial:** " + "; ".join(cov["partial"]))
    lines.append("**🔴 Out of reach:** " + "; ".join(cov["structurally_out"]))
    lines.append("")
    lines.append(f"_{cov['note']}_")
    lines.append("")

    # Sources + disclaimer
    lines.append("## Sources")
    for s in pack.sources:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("---")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


# ── structured output (the "refined data" record) ───────────────────────────
RESEARCH_SCHEMA_VERSION = "research-v2"


def _filing_dict(f: Optional[Filing]) -> Optional[dict]:
    if f is None:
        return None
    return {
        "form": f.form,
        "filed": f.filing_date,
        "period": f.report_date,
        "items": edgar.decode_items(f.items),
        "url": f.url,
    }


def coverage_manifest(pack: ResearchPack) -> dict:
    """The pack's self-declared coverage — what it observed (✅), what's partial (🟡), and
    what is structurally out of reach (🔴). Turns the honest boundary into a visible feature:
    a reader sees exactly what evidence base the analysis rests on and what no $0 tool (and,
    for the 🔴 items, no tool at all) can see. Covered items reflect what actually resolved
    for THIS issuer; partial/out are the standing structural limits (DATA_SOURCES.md)."""
    q = pack.quant or {}
    covered = []
    if pack.trend:
        covered.append("Fundamentals & financial trend (SEC XBRL)")
    if q.get("valuation"):
        covered.append("Valuation & quality factors (computed)")
    if isinstance(q.get("price"), dict):
        covered.append("Price action / technicals — EOD, demo-labeled (§5)")
    if pack.filings:
        covered.append("Official filings — 10-K/10-Q/8-K, item-decoded")
    if pack.qualitative:
        covered.append("Qualitative signal — themes / guidance / tone / risk (filings-derived)")
    if pack.news:
        covered.append("News headlines — link-only (§4)")
    own = pack.ownership or {}
    if own.get("insider_transactions") or own.get("large_holder_filings"):
        covered.append("Insider transactions (Form 4, open-market P/S flagged) + 13D/G filings")
    if own.get("insider_pattern"):
        covered.append("Insider behavioral pattern (cluster buys, net discretionary flow)")
    if pack.quality_flags:
        covered.append("Earnings-quality flags — accruals, cash conversion, margin/growth trajectory")
    if pack.risk_delta:
        covered.append("Risk-factor delta — 10-K Item 1A year-over-year (added/removed risks)")
    partial = [
        "Management commentary — headline + link only (transcripts / interviews are copyrighted)",
        "Regulatory / legal / litigation events — via filings + headlines",
        "Short interest — US biweekly (FINRA); not yet wired",
    ]
    if not (own.get("insider_transactions") or own.get("large_holder_filings")):
        partial.append("Insider / large-holder activity (Form 4, 13D/G) — not wired for this issuer")
    return {
        "covered": covered,
        "partial": partial,
        "structurally_out": [
            "Analyst consensus, price targets, estimate revisions (proprietary)",
            "Real-time quotes / intraday / options-implied volatility (licensed feed)",
            "Full earnings-call transcripts (copyright)",
            "Private positioning, sentiment, rumor, algo / dark-pool flow (unobservable by anyone)",
        ],
        "note": (
            "A research tool covers the observable, documented evidence base and names its "
            "blind spots — it does not, and cannot, capture every driver of price."
        ),
    }


def attach_qualitative(record: dict, block: Optional[dict]) -> dict:
    """Merge an extracted QualitativeBlock dump into an existing research record (in place).
    Used by the qualitative extraction step and the periodic refresh's partial updates."""
    record["qualitative"] = block
    return record


def to_record(pack: ResearchPack) -> dict:
    """Machine-readable research record — the structured, source-linked data you load
    and analyze. Typed groups, ``None`` where a fact didn't resolve (never a bogus 0).
    JSON-serializable; ``qualitative`` is populated by Layer 2 (filings-derived signal)."""
    p = pack.profile
    ticker = p.tickers[0] if p.tickers else pack.query.upper()
    read = earnings_read(pack.filings)

    as_of = None
    if pack.quant and isinstance(pack.quant.get("price"), dict):
        as_of = pack.quant["price"].get("as_of")
    as_of = as_of or date.today().isoformat()

    return {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "as_of": as_of,
        "ticker": ticker,
        "name": p.name,
        "language": pack.language,
        "last_event": _filing_dict(pack.filings[0]) if pack.filings else None,
        "snapshot": {"exchange": p.exchanges, "industry": p.sic_description, "cik": p.cik},
        "quant": pack.quant,
        "trend": [
            {
                "period": r.period, "end": r.end, "revenue": r.revenue,
                "revenue_yoy_pct": r.revenue_yoy_pct, "gross_margin": r.gross_margin,
                "operating_margin": r.operating_margin, "net_margin": r.net_margin,
                "eps_diluted": r.eps_diluted,
            }
            for r in pack.trend
        ],
        "earnings_read": {k: _filing_dict(v) for k, v in read.items()},
        "filings": [_filing_dict(f) for f in pack.filings],
        "news": [
            {"headline": n.headline, "url": n.url, "source": n.source, "date": n.date}
            for n in pack.news
        ],
        "qualitative": pack.qualitative,  # Layer 2 — filings-derived themes / guidance / tone / risk
        "ownership": pack.ownership,       # insider Form 4 + large-holder 13D/G
        "quality_flags": pack.quality_flags,  # earnings-quality observations (refined signal)
        "risk_delta": pack.risk_delta,     # 10-K Item 1A YoY change
        "coverage": coverage_manifest(pack),
        "sources": pack.sources,
        "disclaimer": (
            "Research starting point compiled from public SEC filings — descriptive only, "
            "not investment advice (§10). Verify against the linked primary sources before acting."
        ),
    }


def to_page_dict(pack: ResearchPack) -> dict:
    """The shape the static page builder AND the search backend both emit, consumed by the
    frontend ``render()``. Keyed for the renderer (flat snapshot fields, dataclass rows as
    dicts, 8-K item labels precomputed). One source of truth so featured + searched tickers
    render identically."""
    from dataclasses import asdict, is_dataclass

    d = lambda o: asdict(o) if is_dataclass(o) else o
    er = earnings_read(pack.filings)
    p = pack.profile
    return {
        "ticker": p.tickers[0] if p.tickers else pack.query.upper(),
        "name": p.name,
        "exchanges": p.exchanges,
        "industry": p.sic_description,
        "cik": p.cik,
        "language": pack.language,
        "price": d(pack.price),
        "trend": [d(r) for r in pack.trend],
        "earnings_read": {k: d(v) for k, v in er.items()},
        "filings": [{**d(f), "labels": edgar.decode_items(f.items)} for f in pack.filings],
        "news": [d(n) for n in pack.news],
        "quant": pack.quant,
        "qualitative": pack.qualitative,
        "ownership": pack.ownership,
        "quality_flags": pack.quality_flags,
        "risk_delta": pack.risk_delta,
        "coverage": coverage_manifest(pack),
        "sources": pack.sources,
    }
