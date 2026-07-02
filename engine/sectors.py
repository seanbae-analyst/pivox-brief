"""US + Korea market / sector / HOT-mover data for the morning brief — the readable layer.

The positioning/rates layer (engine/market.py) is institutional and jargon-heavy. This adds
what a normal reader wants: indices, US sector ETFs, and — the part people actually open the
mail for — the HOT movers: today's biggest movers among a buzzy universe of retail/momentum
names (US + KR), ranked by absolute 1-day move so it's never a stale hardcoded list. One
batched yfinance call (~2s), degrades to None on failure.

yfinance is already a project dependency (engine/prices.py); same posture. Not a primary/
official source — labeled as market-data, descriptive.
"""
from __future__ import annotations

import warnings

# (label, yahoo symbol, group)
_US = [
    ("S&P 500", "^GSPC", "지수"),
    ("나스닥", "^IXIC", "지수"),
    ("반도체·AI", "SMH", "섹터"),
    ("빅테크", "XLK", "섹터"),
    ("2차전지·EV", "LIT", "섹터"),
    ("에너지", "XLE", "섹터"),
    ("전력·유틸", "XLU", "섹터"),
]
_KR = [
    ("코스피", "^KS11", "지수"),
    ("코스닥", "^KQ11", "지수"),
    ("원/달러", "KRW=X", "환율"),
]
_HOT_N = 5  # how many movers to surface per market
# sanity bounds — a move beyond these is almost certainly a bad data point (split artifact,
# wrong series, feed glitch). Real index/large-cap moves stay well inside; we'd rather drop a
# value than print a garbage number to a reader who trusts it.
_MAX_1D, _MAX_5D = 45.0, 70.0


def _is_kr(sym: str) -> bool:
    return sym.endswith(".KS") or sym.endswith(".KQ")


def _sane(chg: float | None, cap: float) -> float | None:
    return chg if (chg is not None and abs(chg) <= cap) else None


def _moves(data, rows: list[tuple]) -> list[dict]:
    out: list[dict] = []
    for label, sym, group in rows:
        try:
            s = data[sym].dropna()
        except Exception:
            continue
        if len(s) < 6:
            continue
        last = float(s.iloc[-1])
        out.append({
            "label": label, "group": group, "last": last,
            "chg5_pct": _sane(round(100 * (last / float(s.iloc[-6]) - 1), 1), _MAX_5D),
            "chg1_pct": _sane(round(100 * (last / float(s.iloc[-2]) - 1), 1), _MAX_1D) if len(s) >= 2 else None,
            "as_of": str(s.index[-1].date()),
        })
    return out


def _hot(data, rows: list[tuple]) -> list[dict]:
    """Biggest movers by absolute 1-day move (today's hot names — gainers and losers)."""
    items = []
    for label, sym in rows:
        try:
            s = data[sym].dropna()
        except Exception:
            continue
        if len(s) < 2:
            continue
        last = float(s.iloc[-1])
        c1 = _sane(round(100 * (last / float(s.iloc[-2]) - 1), 1), _MAX_1D)
        if c1 is None:   # bad data point → don't let it rank as a "hot mover"
            continue
        c5 = _sane(round(100 * (last / float(s.iloc[-6]) - 1), 1), _MAX_5D) if len(s) >= 6 else None
        spark = [round(float(v), 4) for v in s.tail(12).tolist()]  # recent closes → sparkline
        items.append({"label": label, "symbol": sym, "last": last, "chg1_pct": c1, "chg5_pct": c5,
                      "spark": spark, "as_of": str(s.index[-1].date())})
    items.sort(key=lambda i: abs(i["chg1_pct"]), reverse=True)
    return items[:_HOT_N]


def build_sectors() -> dict | None:
    from engine.watchlist import resolve
    universe = resolve()  # the user's chosen themes + custom tickers
    us_hot_u = [(n, s) for n, s in universe if not _is_kr(s)]
    kr_hot_u = [(n, s) for n, s in universe if _is_kr(s)]

    syms = [s for _, s, _ in _US + _KR] + [s for _, s in universe]
    try:
        import yfinance as yf
        warnings.filterwarnings("ignore")
        data = yf.download(syms, period="12d", progress=False, threads=True)["Close"]
    except Exception:
        return None
    us, kr = _moves(data, _US), _moves(data, _KR)
    us_hot, kr_hot = _hot(data, us_hot_u), _hot(data, kr_hot_u)
    if not (us or kr or us_hot or kr_hot):
        return None
    return {
        "us": us, "kr": kr, "us_hot": us_hot, "kr_hot": kr_hot,
        "us_as_of": us[0]["as_of"] if us else None,
        "kr_as_of": kr[0]["as_of"] if kr else None,
    }
