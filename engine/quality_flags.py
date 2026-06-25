"""Earnings-quality & fundamental-anomaly flags — Wave-1 refined signal (STRATEGY.md).

DESCRIPTIVE observations derived from the XBRL we already pull — the checks an analyst does by
hand that free aggregators don't surface: does cash back the earnings (accruals / cash
conversion), which way are margins and growth trending, is the share count rising or falling.

Every flag is an **observation + its number + the basis** — never a verdict (§10: the reader
draws the conclusion). Pure functions over already-fetched data (a QuarterRow-like trend +
engine.edgar.extended_facts), so they unit-test offline. A flag is omitted when inputs are absent.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from engine.edgar import FinancialSeries


def _latest(series: Optional[FinancialSeries]) -> Optional[float]:
    return series.points[-1].val if series and series.points else None


def _direction(vals: list, eps: float = 0.0) -> str:
    """Plain-language trajectory of a short series (oldest → newest)."""
    xs = [v for v in vals if v is not None]
    if len(xs) < 2:
        return "n/a"
    delta = xs[-1] - xs[0]
    if abs(delta) <= eps:
        return "flat"
    return "rising" if delta > 0 else "falling"


def _seq(vals: list, suffix: str = "", signed: bool = False) -> str:
    def fmt(v):
        if v is None:
            return "—"
        return (f"{v:+g}" if signed else f"{v:g}") + suffix
    return " → ".join(fmt(v) for v in vals)


def quality_flags(trend: list, ext: dict[str, FinancialSeries]) -> list[dict]:
    """Build the descriptive flag list. ``trend`` = QuarterRow-like rows (.net_margin /
    .operating_margin / .revenue_yoy_pct, oldest→newest). ``ext`` = engine.edgar.extended_facts."""
    out: list[dict] = []

    # ── cash quality (latest fiscal year, consistent basis) ───────────────────
    # Conversion ratios (OCF/NI, FCF/NI) and the accrual gap are only meaningful for a profit;
    # for a net loss they invert or read as nonsense (e.g. "OCF was -3.2x net income"), so we
    # emit a neutral loss observation instead.
    ni = _latest(ext.get("net_income_annual"))
    ocf = _latest(ext.get("ocf"))
    capex = _latest(ext.get("capex"))
    if ni is not None and ocf is not None:
        if ni > 0:
            gap = round((ni - ocf) / ni * 100.0, 1)
            out.append({
                "key": "accrual_gap", "label": "Accrual gap (NI vs OCF)", "value": gap, "unit": "%",
                "observation": f"Annual net income {'exceeded' if gap > 0 else 'trailed'} operating "
                               f"cash flow by {abs(gap)}% (accrual gap).",
                "basis": "latest FY net income vs operating cash flow",
            })
            out.append({
                "key": "cash_conversion", "label": "Cash conversion (OCF/NI)", "value": round(ocf / ni, 2), "unit": "x",
                "observation": f"Operating cash flow was {round(ocf / ni, 2)}x net income.",
                "basis": "latest FY",
            })
            if capex is not None:
                fcf = ocf - capex
                out.append({
                    "key": "fcf_conversion", "label": "FCF conversion (FCF/NI)", "value": round(fcf / ni, 2), "unit": "x",
                    "observation": f"Free cash flow (OCF − capex) was {round(fcf / ni, 2)}x net income.",
                    "basis": "latest FY",
                })
        else:
            out.append({
                "key": "net_loss", "label": "Net loss (latest FY)", "value": round(ni, 0), "unit": None,
                "observation": "Latest fiscal year recorded a net loss; cash-conversion and accrual "
                               f"ratios are not meaningful (operating cash flow was {round(ocf, 0):,.0f}).",
                "basis": "latest FY",
            })

    # ── trajectories (quarterly trend) ────────────────────────────────────────
    if trend and len(trend) >= 2:
        nm = [getattr(r, "net_margin", None) for r in trend]
        yoy = [getattr(r, "revenue_yoy_pct", None) for r in trend]
        if any(v is not None for v in nm):
            d = _direction(nm)
            out.append({
                "key": "net_margin_trend", "label": "Net margin trajectory", "value": d, "unit": None,
                "observation": f"Net margin over last {len(trend)} quarters: {_seq(nm, '%')} ({d}).",
                "basis": "quarterly",
            })
        if any(v is not None for v in yoy):
            d = _direction(yoy)
            out.append({
                "key": "rev_growth_trend", "label": "Revenue-growth trajectory", "value": d, "unit": None,
                "observation": f"Revenue YoY over last {len(trend)} quarters: {_seq(yoy, '%', signed=True)} "
                               f"({d} growth rate).",
                "basis": "quarterly YoY",
            })

    # ── share count (dilution vs buyback), YoY ────────────────────────────────
    shares = ext.get("shares")
    if shares and len(shares.points) >= 2:
        last = shares.points[-1]
        target = date.fromisoformat(last.end) - timedelta(days=365)
        best, best_diff = None, 60
        for p in shares.points[:-1]:
            diff = abs((date.fromisoformat(p.end) - target).days)
            if diff < best_diff:
                best, best_diff = p, diff
        if best and best.val:
            chg = round((last.val / best.val - 1.0) * 100.0, 1)
            out.append({
                "key": "share_count_change", "label": "Share count YoY", "value": chg, "unit": "%",
                "observation": f"Shares outstanding {'shrank' if chg < 0 else 'grew'} {abs(chg)}% YoY "
                               f"({'net buyback' if chg < 0 else 'net dilution'}).",
                "basis": "shares outstanding, YoY",
            })
    return out
