"""Offline unit tests for the Layer-1 quant factor math (engine/factors.py).

Pure computation over synthetic EDGAR series — no network, no API key. Locks the
basis convention (TTM income statement / annual cash flow / instant balance sheet)
and the None-pruning behavior so a missing tag degrades gracefully.
"""

from __future__ import annotations

from engine.edgar import FactPoint, FinancialSeries
from engine import factors


def series(pairs: list[tuple[str, float]]) -> FinancialSeries:
    """Build a FinancialSeries from (period_end, value) pairs, ascending by end."""
    pts = [FactPoint(end=e, val=v, fy=None, fp=None, form="10-Q", frame=None, start=None) for e, v in pairs]
    return FinancialSeries(concept="test", points=pts)


def test_ttm_sums_last_four_quarters():
    s = series([("2025-03-31", 10.0), ("2025-06-30", 20.0), ("2025-09-30", 30.0),
                ("2025-12-31", 40.0), ("2026-03-31", 50.0)])
    assert factors._ttm(s) == 140.0  # last 4 = 20+30+40+50


def test_ttm_needs_four_points():
    assert factors._ttm(series([("2025-12-31", 10.0)])) is None
    assert factors._ttm(None) is None


def test_total_debt_prefers_single_tag_then_synthesizes():
    ext = {"debt_total": series([("2026-03-28", 82.0)])}
    assert factors.total_debt(ext) == 82.0
    ext2 = {"debt_noncurrent": series([("2026-03-28", 74.0)]),
            "debt_current": series([("2026-03-28", 8.0)])}
    assert factors.total_debt(ext2) == 82.0
    assert factors.total_debt({}) is None


def _four(q):
    """Four equal quarterly points → TTM = 4*q (helper for a clean round number)."""
    return series([("2025-06-30", q), ("2025-09-30", q), ("2025-12-31", q), ("2026-03-31", q)])


def test_compute_quant_core_ratios():
    fin = {
        "revenue": _four(100.0),         # TTM revenue 400
        "net_income": _four(25.0),       # TTM NI 100
        "eps_diluted": _four(1.0),       # TTM EPS 4.0
        "operating_income": _four(30.0),
        "gross_profit": _four(50.0),
    }
    ext = {
        "shares": series([("2025-03-31", 110.0), ("2026-03-31", 100.0)]),  # -9.1% YoY
        "equity": series([("2026-03-31", 200.0)]),
        "cash": series([("2026-03-31", 50.0)]),
        "debt_total": series([("2026-03-31", 80.0)]),
        "current_assets": series([("2026-03-31", 150.0)]),
        "current_liabs": series([("2026-03-31", 100.0)]),
        "ocf": series([("2025-12-31", 120.0)]),
        "capex": series([("2025-12-31", 20.0)]),       # FCF 100
        "dividends": series([("2025-12-31", 10.0)]),
        "buybacks": series([("2025-12-31", 30.0)]),
        "da": series([("2025-12-31", 10.0)]),
        "revenue_annual": series([("2025-12-31", 400.0)]),
        "operating_income_annual": series([("2025-12-31", 120.0)]),  # EBITDA 130
    }
    block = factors.compute_quant(fin, ext, price=40.0)

    val = block["valuation"]
    assert val["market_cap"] == 4000.0          # 100 shares * 40
    assert val["pe_ttm"] == 10.0                # 40 / 4.0
    assert val["ps_ttm"] == 10.0                # 4000 / 400
    assert val["pb"] == 20.0                    # 4000 / 200
    # EV = 4000 + 80 - 50 = 4030; EBITDA = 120 + 10 = 130 -> 31.0
    assert val["ev_ebitda"] == 31.0
    assert val["fcf_yield_pct"] == 2.5          # 100 / 4000
    assert val["dividend_yield_pct"] == 0.2     # 10 / 4000 (rounds to 0.2)

    prof = block["profitability"]
    assert prof["net_margin_ttm_pct"] == 25.0   # 100 / 400
    assert prof["operating_margin_ttm_pct"] == 30.0
    assert prof["fcf_margin_pct"] == 25.0       # 100 / 400
    assert prof["roe_pct"] == 50.0              # 100 / 200

    health = block["health"]
    assert health["net_debt"] == 30.0           # 80 - 50
    assert health["debt_to_equity"] == 0.4
    assert health["current_ratio"] == 1.5

    cap = block["capital_return"]
    assert cap["shares_yoy_pct"] == -9.1        # 100/110 - 1


def test_compute_quant_degrades_without_inputs():
    """Missing series / no price → None factors, never a crash or a bogus zero."""
    block = factors.compute_quant({}, {}, price=None)
    assert block["valuation"]["market_cap"] is None
    assert block["valuation"]["pe_ttm"] is None
    assert block["health"]["net_debt"] is None
    assert "price" not in block                  # no technicals passed


def test_negative_eps_yields_no_pe():
    fin = {"revenue": _four(100.0), "eps_diluted": _four(-1.0)}
    block = factors.compute_quant(fin, {}, price=40.0)
    assert block["valuation"]["pe_ttm"] is None  # loss-making → P/E omitted, not negative
