"""US + Korea market / sector moves for the morning brief — the readable layer.

The positioning/rates layer (engine/market.py) is institutional and jargon-heavy. This adds
the thing a normal reader actually wants: "what did the US market and the Korean market do,
and which sectors moved" — indices, sector ETFs (US), and bellwether large caps (KR), each as
a plain 1-day and 5-day % move. One batched yfinance call (~1-2s), degrades to None on failure.

yfinance is already a project dependency (engine/prices.py uses it for earnings reactions); same
posture here. Not a primary/official source — labeled as market-data, descriptive.
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
    ("삼성전자", "005930.KS", "반도체"),
    ("SK하이닉스", "000660.KS", "반도체"),
    ("LG에너지솔루션", "373220.KS", "2차전지"),
    ("현대차", "005380.KS", "자동차"),
]


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
        chg5 = round(100 * (last / float(s.iloc[-6]) - 1), 1)
        chg1 = round(100 * (last / float(s.iloc[-2]) - 1), 1) if len(s) >= 2 else None
        out.append({
            "label": label, "group": group, "last": last,
            "chg5_pct": chg5, "chg1_pct": chg1,
            "as_of": str(s.index[-1].date()),
        })
    return out


def build_sectors() -> dict | None:
    syms = [s for _, s, _ in _US + _KR]
    try:
        import yfinance as yf
        warnings.filterwarnings("ignore")
        data = yf.download(syms, period="12d", progress=False, threads=True)["Close"]
    except Exception:
        return None
    us, kr = _moves(data, _US), _moves(data, _KR)
    if not us and not kr:
        return None
    return {
        "us": us, "kr": kr,
        "us_as_of": us[0]["as_of"] if us else None,
        "kr_as_of": kr[0]["as_of"] if kr else None,
    }
