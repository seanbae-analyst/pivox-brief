"""Quantitative factor computation for the research pack — Layer 1 (RESEARCH_PACK_PLAN.md).

Turns already-fetched EDGAR series (engine.edgar) + an optional demo price snapshot
(engine.prices) into the valuation / profitability / health / capital-return factors a
reader uses to judge whether a stock is cheap, healthy, and returning capital. The math
is pure (no I/O) so it unit-tests offline; ``compute_quant`` is the thin assembler.

Every factor is ``None`` when its inputs are absent — the renderer shows only what
resolved (same philosophy as ``research_pack.build_trend``). Not investment advice (§10):
these are descriptive ratios over public filings, not a recommendation.

Basis convention (see engine.edgar parsers — each item is filed on the basis that's
reliable for it, and mixing is the standard practice for trailing multiples):
- **TTM** (sum of last 4 discrete quarters): income statement — revenue, net income,
  EPS, operating income.
- **ANNUAL** (latest fiscal year): cash-flow items — OCF, capex, dividends, buybacks,
  D&A — whose interim figures are fiscal-YTD cumulative (summing quarters double-counts).
- **INSTANT** (latest balance sheet): equity, cash, debt, shares, current assets/liabs.
Market cap and enterprise value use the *current* price + *latest* balance sheet, which
is the convention even when the paired earnings figure is TTM or annual.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from engine.edgar import FinancialSeries


# ── basis helpers ─────────────────────────────────────────────────────────────
def _ttm(series: Optional[FinancialSeries]) -> Optional[float]:
    """Trailing twelve months = sum of the last 4 discrete quarterly points."""
    if not series or len(series.points) < 4:
        return None
    return sum(p.val for p in series.points[-4:])


def _latest(series: Optional[FinancialSeries]) -> Optional[float]:
    return series.points[-1].val if series and series.points else None


def _instant_yoy(series: Optional[FinancialSeries], days: int = 365, tol: int = 50) -> Optional[float]:
    """Pct change of an instant series' latest value vs ~``days`` earlier (by end date).
    Drives the shares-outstanding trend (a buyback / dilution signal)."""
    if not series or len(series.points) < 2:
        return None
    last = series.points[-1]
    target = date.fromisoformat(last.end) - timedelta(days=days)
    best, best_diff = None, tol
    for p in series.points[:-1]:
        diff = abs((date.fromisoformat(p.end) - target).days)
        if diff < best_diff:
            best, best_diff = p, diff
    if best and best.val:
        return round((last.val / best.val - 1.0) * 100.0, 1)
    return None


def _ratio(numer: Optional[float], denom: Optional[float], *, pct: bool = False, nd: int = 2) -> Optional[float]:
    if numer is None or not denom:
        return None
    r = numer / denom
    return round(r * 100.0, 1) if pct else round(r, nd)


def total_debt(ext: dict[str, FinancialSeries]) -> Optional[float]:
    """Prefer the non-current + current synthesis (always the true total); fall back to the
    single ``LongTermDebt`` tag only if the components are absent — that tag is the *noncurrent*
    carrying amount for many issuers, so preferring it would understate total debt / D/E."""
    nc = _latest(ext.get("debt_noncurrent"))
    cu = _latest(ext.get("debt_current"))
    if nc is not None or cu is not None:
        return (nc or 0.0) + (cu or 0.0)
    return _latest(ext.get("debt_total"))


# ── factor assembly ─────────────────────────────────────────────────────────
def compute_quant(
    fin: dict[str, FinancialSeries],
    ext: dict[str, FinancialSeries],
    price: Optional[float] = None,
    technicals: Optional[object] = None,
) -> dict:
    """Assemble the Layer-1 quant block. ``fin`` = engine.edgar.financials (>=4 quarters),
    ``ext`` = engine.edgar.extended_facts, ``price`` = latest close (demo), ``technicals``
    = engine.prices.Technicals | None. Returns a nested dict of factor groups (None-pruned
    at render time, not here, so the shape is stable for the typed schema)."""
    # TTM income statement
    ttm_revenue = _ttm(fin.get("revenue"))
    ttm_net_income = _ttm(fin.get("net_income"))
    ttm_oper_income = _ttm(fin.get("operating_income"))
    ttm_gross_profit = _ttm(fin.get("gross_profit"))

    # Latest balance sheet (instant)
    shares = _latest(ext.get("shares"))
    equity = _latest(ext.get("equity"))
    cash = _latest(ext.get("cash"))
    debt = total_debt(ext)
    cur_assets = _latest(ext.get("current_assets"))
    cur_liabs = _latest(ext.get("current_liabs"))

    # Annual cash-flow (latest fiscal year)
    ann_ocf = _latest(ext.get("ocf"))
    ann_capex = _latest(ext.get("capex"))
    ann_div = _latest(ext.get("dividends"))
    ann_buyback = _latest(ext.get("buybacks"))
    ann_da = _latest(ext.get("da"))
    ann_revenue = _latest(ext.get("revenue_annual"))
    ann_oper_income = _latest(ext.get("operating_income_annual"))

    market_cap = (shares * price) if (shares and price) else None
    enterprise_value = None
    if market_cap is not None and debt is not None and cash is not None:
        enterprise_value = market_cap + debt - cash

    # FCF on a consistent annual basis (OCF − capex).
    ann_fcf = (ann_ocf - ann_capex) if (ann_ocf is not None and ann_capex is not None) else None

    # EBITDA only when operating income and D&A are from the SAME fiscal year (each is "latest
    # annual" independently and a tag can lag a year — summing two different years is wrong).
    oi_s, da_s = ext.get("operating_income_annual"), ext.get("da")
    ebitda = None
    if (ann_oper_income is not None and ann_da is not None
            and oi_s and da_s and oi_s.points[-1].end == da_s.points[-1].end):
        ebitda = ann_oper_income + ann_da

    valuation = {
        "market_cap": round(market_cap, 0) if market_cap else None,
        # P/E = market cap / TTM net income (NOT a sum of quarterly per-share EPS, which is
        # invalid when share count changes across the year).
        "pe_ttm": _ratio(market_cap, ttm_net_income) if (market_cap and ttm_net_income and ttm_net_income > 0) else None,
        "ps_ttm": _ratio(market_cap, ttm_revenue),
        "pb": _ratio(market_cap, equity),
        "ev_ebitda": _ratio(enterprise_value, ebitda) if (ebitda and ebitda > 0) else None,
        "fcf_yield_pct": _ratio(ann_fcf, market_cap, pct=True),
        "dividend_yield_pct": _ratio(ann_div, market_cap, pct=True),
        "buyback_yield_pct": _ratio(ann_buyback, market_cap, pct=True),
        "ev_basis": "EV uses current price + latest balance sheet; EBITDA = latest annual operating "
                    "income + D&A (same FY). Market cap uses cover-page shares of ONE class — "
                    "multi-class issuers (e.g. GOOGL, BRK) are understated.",
    }
    profitability = {
        "gross_margin_ttm_pct": _ratio(ttm_gross_profit, ttm_revenue, pct=True),
        "operating_margin_ttm_pct": _ratio(ttm_oper_income, ttm_revenue, pct=True),
        "net_margin_ttm_pct": _ratio(ttm_net_income, ttm_revenue, pct=True),
        "fcf_margin_pct": _ratio(ann_fcf, ann_revenue, pct=True),
        "roe_pct": _ratio(ttm_net_income, equity, pct=True),
    }
    health = {
        "cash": round(cash, 0) if cash is not None else None,
        "total_debt": round(debt, 0) if debt is not None else None,
        "net_debt": round(debt - cash, 0) if (debt is not None and cash is not None) else None,
        "debt_to_equity": _ratio(debt, equity),
        "current_ratio": _ratio(cur_assets, cur_liabs),
    }
    capital_return = {
        "dividends_annual": round(ann_div, 0) if ann_div is not None else None,
        "buybacks_annual": round(ann_buyback, 0) if ann_buyback is not None else None,
        "shares_outstanding": round(shares, 0) if shares is not None else None,
        "shares_yoy_pct": _instant_yoy(ext.get("shares")),
    }

    block = {
        "valuation": valuation,
        "profitability": profitability,
        "health": health,
        "capital_return": capital_return,
        "basis_note": "TTM = last 4 quarters (income statement); annual = latest FY (cash flow); "
                      "instant = latest balance sheet. See engine/factors.py.",
    }
    if technicals is not None:
        block["price"] = {
            "last_close": technicals.last_close,
            "as_of": technicals.as_of,
            "ret_1m_pct": technicals.ret_1m_pct,
            "ret_ytd_pct": technicals.ret_ytd_pct,
            "ret_1y_pct": technicals.ret_1y_pct,
            "high_52w": technicals.high_52w,
            "low_52w": technicals.low_52w,
            "pct_from_52w_high": technicals.pct_from_52w_high,
            "ma50": technicals.ma50,
            "ma200": technicals.ma200,
            "source": "demo (yfinance, DATA_SOURCES.md §5) — not a licensed real-time feed",
        }
    return block
