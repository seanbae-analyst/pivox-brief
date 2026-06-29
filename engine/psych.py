"""Pivox Fear & Greed — a 0-100 market-psychology composite from FREE / OFFICIAL data.

CNN's Fear & Greed Index is proprietary; this rebuilds the idea from sources we can use,
blending six independent mood signals (each normalized to 0 = extreme fear … 100 = extreme
greed) and averaging them. It also returns the per-signal breakdown so the brief can show
*why* the needle sits where it does — which is the actual market-psychology read.

Signals (8 — CNN-level coverage from free sources):
  1. 주가 모멘텀     — S&P 500 5-day return (FRED SP500)
  2. 변동성(VIX)     — VIX level (FRED VIXCLS); low vol = greed
  3. 변동성 만기구조 — VIX / VIX-3M (VIXCLS / VXVCLS); backwardation = fear
  4. 신용 스프레드   — high-yield OAS (BAMLH0A0HYM2); tight = greed
  5. 금융 스트레스   — St. Louis Fed Financial Stress Index (STLFSI4); negative = calm
  6. 크립토 심리     — crypto Fear & Greed (alternative.me, keyless) as a risk-appetite proxy
  7. 시장 폭         — % of a large-cap basket above its 50-day MA (yfinance); broad = greed
  8. 안전자산 선호   — stocks (SPY) vs bonds (TLT) 20-day return spread (yfinance); stocks-win = greed

7 & 8 mirror CNN's "stock price strength/breadth" and "safe-haven demand" components. Every
signal degrades independently (a dead source just drops out of the average), and the score is
None only if nothing resolves.
"""
from __future__ import annotations

import os

import requests

from engine.market import _TIMEOUT, _UA, _fred_obs

# ~28 S&P 500 leaders — broad enough for a meaningful breadth read, cheap enough for one fetch
_BREADTH_BASKET = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AVGO", "TSLA", "JPM", "V",
    "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "COST", "ORCL", "LLY",
    "BAC", "KO", "PEP", "NFLX", "AMD", "CRM", "ADBE", "CVX",
]


def _yf_factors() -> dict:
    """Breadth (% of basket > 50d MA) + safe-haven demand (SPY vs TLT 20d). One yfinance call."""
    try:
        import warnings

        import yfinance as yf
        warnings.filterwarnings("ignore")
        data = yf.download(_BREADTH_BASKET + ["SPY", "TLT"], period="4mo",
                           progress=False, threads=True)["Close"]
    except Exception:
        return {}
    out: dict = {}
    above = tot = 0
    for s in _BREADTH_BASKET:
        try:
            ser = data[s].dropna()
        except Exception:
            continue
        if len(ser) >= 50:
            tot += 1
            if float(ser.iloc[-1]) > float(ser.tail(50).mean()):
                above += 1
    if tot >= 10:
        out["breadth"] = (round(100 * above / tot), f"{above}/{tot}개 50일선 위")
    try:
        spy, tlt = data["SPY"].dropna(), data["TLT"].dropna()
        if len(spy) >= 21 and len(tlt) >= 21:
            r_spy = 100 * (float(spy.iloc[-1]) / float(spy.iloc[-21]) - 1)
            r_tlt = 100 * (float(tlt.iloc[-1]) / float(tlt.iloc[-21]) - 1)
            out["safehaven"] = (r_spy - r_tlt, f"주식−채권 20일 {r_spy - r_tlt:+.1f}%p")
    except Exception:
        pass
    return out


def _latest(key: str, sid: str) -> float | None:
    obs = _fred_obs(key, sid, 1)
    if not obs:
        return None
    try:
        return float(obs[0]["value"])
    except (TypeError, ValueError, KeyError):
        return None


def _series(key: str, sid: str, n: int) -> list[float]:
    out = []
    for o in _fred_obs(key, sid, n) or []:  # newest first
        try:
            out.append(float(o["value"]))
        except (TypeError, ValueError, KeyError):
            pass
    return out


def _crypto_fng() -> int | None:
    try:
        d = requests.get("https://api.alternative.me/fng/?limit=1", headers=_UA, timeout=_TIMEOUT).json()
        return int(d["data"][0]["value"])
    except Exception:
        return None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """Map x from [x0,x1] onto [y0,y1], clamped. x0→y0, x1→y1 (x0/x1 may be inverted)."""
    if x1 == x0:
        return y0
    t = _clamp((x - x0) / (x1 - x0), 0.0, 1.0)
    return y0 + t * (y1 - y0)


def _label(score: int) -> str:
    return ("극단적 공포" if score < 25 else "공포" if score < 45
            else "중립" if score <= 55 else "탐욕" if score <= 75 else "극단적 탐욕")


def fear_greed() -> dict | None:
    key = os.environ.get("FRED_API_KEY")
    comp: list[tuple[str, int, str]] = []

    spx = _series(key, "SP500", 8) if key else []
    if len(spx) >= 6 and spx[5]:
        chg5 = 100 * (spx[0] / spx[5] - 1)
        comp.append(("주가 모멘텀", round(_lerp(chg5, -4, 4, 0, 100)), f"S&P 5일 {chg5:+.1f}%"))

    vix = _latest(key, "VIXCLS") if key else None
    if vix is not None:
        comp.append(("변동성(VIX)", round(_lerp(vix, 32, 12, 0, 100)), f"VIX {vix:.1f}"))

    vix3 = _latest(key, "VXVCLS") if key else None
    if vix is not None and vix3:
        ratio = vix / vix3
        comp.append(("변동성 만기구조", round(_lerp(ratio, 1.05, 0.85, 0, 100)),
                     f"VIX/3M {ratio:.2f}" + ("·백워데이션" if ratio > 1 else "·콘탱고")))

    hy = _latest(key, "BAMLH0A0HYM2") if key else None
    if hy is not None:
        comp.append(("신용 스프레드", round(_lerp(hy, 6, 2.5, 0, 100)), f"HY {hy:.2f}%"))

    stl = _latest(key, "STLFSI4") if key else None
    if stl is not None:
        comp.append(("금융 스트레스", round(_lerp(stl, 1, -1, 0, 100)), f"StL {stl:+.2f}"))

    cf = _crypto_fng()
    if cf is not None:
        comp.append(("크립토 심리", _clamp(cf, 0, 100), f"코인 F&G {cf}"))

    yf = _yf_factors()
    if "breadth" in yf:
        sc, nt = yf["breadth"]
        comp.append(("시장 폭", sc, nt))
    if "safehaven" in yf:
        diff, nt = yf["safehaven"]
        comp.append(("안전자산 선호", round(_lerp(diff, -8, 8, 0, 100)), nt))

    if not comp:
        return None
    score = round(sum(c[1] for c in comp) / len(comp))
    return {
        "score": score,
        "label": _label(score),
        "components": [{"name": n, "score": s, "note": nt} for n, s, nt in comp],
    }
