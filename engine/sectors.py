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
# buzzy universes — the brief shows the biggest movers from these each day (not all of them)
_US_HOT = [
    ("엔비디아", "NVDA"), ("테슬라", "TSLA"), ("팔란티어", "PLTR"), ("AMD", "AMD"),
    ("코인베이스", "COIN"), ("슈마이", "SMCI"), ("애플", "AAPL"), ("메타", "META"),
    ("마스트", "MSTR"), ("브로드컴", "AVGO"), ("넷플릭스", "NFLX"), ("아마존", "AMZN"),
]
_KR_HOT = [
    ("삼성전자", "005930.KS"), ("SK하이닉스", "000660.KS"), ("에코프로비엠", "247540.KQ"),
    ("에코프로", "086520.KQ"), ("한미반도체", "042700.KS"), ("두산에너빌리티", "034020.KS"),
    ("한화에어로", "012450.KS"), ("알테오젠", "196170.KQ"), ("포스코홀딩스", "005490.KS"),
    ("삼성바이오", "207940.KS"), ("카카오", "035720.KS"), ("네이버", "035420.KS"),
]

_HOT_N = 5  # how many movers to surface per market


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
            "chg5_pct": round(100 * (last / float(s.iloc[-6]) - 1), 1),
            "chg1_pct": round(100 * (last / float(s.iloc[-2]) - 1), 1) if len(s) >= 2 else None,
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
        c1 = round(100 * (last / float(s.iloc[-2]) - 1), 1)
        c5 = round(100 * (last / float(s.iloc[-6]) - 1), 1) if len(s) >= 6 else None
        items.append({"label": label, "chg1_pct": c1, "chg5_pct": c5, "as_of": str(s.index[-1].date())})
    items.sort(key=lambda i: abs(i["chg1_pct"]), reverse=True)
    return items[:_HOT_N]


def build_sectors() -> dict | None:
    syms = [s for _, s, _ in _US + _KR] + [s for _, s in _US_HOT + _KR_HOT]
    try:
        import yfinance as yf
        warnings.filterwarnings("ignore")
        data = yf.download(syms, period="12d", progress=False, threads=True)["Close"]
    except Exception:
        return None
    us, kr = _moves(data, _US), _moves(data, _KR)
    us_hot, kr_hot = _hot(data, _US_HOT), _hot(data, _KR_HOT)
    if not (us or kr or us_hot or kr_hot):
        return None
    return {
        "us": us, "kr": kr, "us_hot": us_hot, "kr_hot": kr_hot,
        "us_as_of": us[0]["as_of"] if us else None,
        "kr_as_of": kr[0]["as_of"] if kr else None,
    }
