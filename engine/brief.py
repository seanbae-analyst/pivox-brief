"""Morning market-psychology brief — compresses the market-context layer into a daily push.

Two products from one build:
  • build_brief()   — the daily digest: one-line regime read + near-real-time tape +
                      positioning extremes + a single "watch" tension, rendered as KO text.
  • detect_alerts() — the "something big happened" trigger: 1-day extremes on the freshest
                      daily series, a yield-curve regime flip, or a newly-crowded position.

State: a small snapshot (data/brief_state.json) persists each run's key numbers so the brief
can say what CHANGED since the prior run (true day-over-day) and suppress quiet days. The
snapshot is the SoT for "new" crowded extremes and curve flips — alerts fire on transitions,
not on standing conditions, so the same crowded trade doesn't re-alert every morning.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from engine.market import _daily_flow, _positioning, _rates, _regime_read

_STATE = Path(__file__).resolve().parent.parent / "data" / "brief_state.json"

# big-event thresholds — 1-day moves on the freshest daily (T+1) series
_ALERT = {
    "S&P 500": ("pct", 2.0, "S&P 500"),
    "Nasdaq": ("pct", 2.5, "나스닥"),
    "VIX": ("level", 4.0, "VIX"),
    "HY spread": ("bp", 25, "HY 크레딧 스프레드"),
    "US dollar": ("pct", 1.5, "달러"),
    "UST 10Y": ("bp", 15, "美 10년물"),
}


# ── small formatters (None-safe) ─────────────────────────────────────────────────
def _pct(x, dp=1):  return "n/a" if x is None else f"{x:+.{dp}f}%"
def _num(x, dp=1):  return "n/a" if x is None else f"{x:.{dp}f}"
def _bp(x):         return "n/a" if x is None else f"{x:+d}bp"
def _sgn(x, dp=1):  return "n/a" if x is None else f"{x:+.{dp}f}"


def _tilt(flow: dict) -> str:
    """Risk-on/off read from the three cleanest 5-day axes (equities, vol, credit)."""
    spx, vix, hy = flow.get("S&P 500"), flow.get("VIX"), flow.get("HY spread")
    sig = 0
    if spx and spx.get("chg5_pct") is not None:
        sig += 1 if spx["chg5_pct"] > 0 else -1
    if vix and vix.get("chg5") is not None:
        sig += 1 if vix["chg5"] < 0 else -1
    if hy and hy.get("chg5_bp") is not None:
        sig += 1 if hy["chg5_bp"] < 0 else -1
    if sig >= 2:
        return "위험선호 우위 (주식↑·변동성↓·크레딧 안정)"
    if sig <= -2:
        return "위험회피 우위 (주식↓·변동성↑·크레딧 부담↑)"
    return "혼조 / 방향성 불명확"


def _load_state() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(snap: dict) -> None:
    try:
        _STATE.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def detect_alerts(flow: dict, rates: dict | None, positioning: list[dict],
                  prior: dict) -> list[str]:
    """The 'something big' trigger. Fires on 1-day extremes + regime transitions vs prior."""
    out: list[str] = []
    # 1) one-day extremes on the daily tape
    for label, (kind, thr, ko) in _ALERT.items():
        f = flow.get(label)
        if not f:
            continue
        if kind == "pct" and f.get("chg1_pct") is not None and abs(f["chg1_pct"]) >= thr:
            out.append(f"{ko} 하루 {f['chg1_pct']:+.1f}% (임계 ±{thr}%)")
        elif kind == "level" and f.get("chg1") is not None and abs(f["chg1"]) >= thr:
            out.append(f"{ko} 하루 {f['chg1']:+.1f}pt → {f['value']:.1f} (임계 ±{thr})")
        elif kind == "bp" and f.get("chg1_bp") is not None and abs(f["chg1_bp"]) >= thr:
            out.append(f"{ko} 하루 {f['chg1_bp']:+d}bp (임계 ±{thr}bp)")
    # 2) yield-curve regime FLIP (transition only)
    cur = (rates or {}).get("curve")
    if cur and prior.get("curve") and cur != prior["curve"]:
        out.append(f"수익률 커브 전환: {prior['curve']} → {cur} (10y-2y {(rates or {}).get('spread_10y_2y'):+})")
    # 3) NEWLY crowded extreme (basis-driven markets excluded — financing, not sentiment)
    now_ext = {p["market"]: p["extreme"] for p in positioning if p.get("extreme") and not p.get("basis")}
    prev_ext = prior.get("extremes", {})
    for mk, ex in now_ext.items():
        if prev_ext.get(mk) != ex:
            out.append(f"신규 포지션 극단: {mk} ({ex})")
    return out


def build_brief(lang: str = "ko") -> dict:
    rates = _rates()
    positioning = _positioning()
    flow_list = _daily_flow() or []
    flow = {f["label"]: f for f in flow_list}
    prior = _load_state()

    pos_ds = [p["days_old"] for p in positioning if p.get("days_old") is not None]
    lag = min(pos_ds) if pos_ds else None
    as_of = (flow_list[0]["as_of"] if flow_list else None) or (rates or {}).get("as_of") or str(date.today())
    headline = _tilt(flow)
    regime = _regime_read(rates, positioning, flow_list)
    extremes = [p for p in positioning if p.get("extreme") and not p.get("basis")]
    alerts = detect_alerts(flow, rates, positioning, prior)

    # single "watch" tension — the most informative cross-signal
    watch = None
    vix = next((p for p in positioning if p["market"] == "VIX"), None)
    hy5 = (flow.get("HY spread") or {}).get("chg5_bp")
    if vix and vix["net"] < 0 and hy5 and hy5 > 0:
        watch = "변동성 숏(안일)인데 크레딧 스프레드는 벌어지는 중 — 안일함 vs 신용부담이 엇갈림."
    elif extremes:
        e = extremes[0]
        watch = f"{e['market']} 포지션이 극단({e['extreme']}) — 평균회귀(반전) 가능성 주시."

    # quiet day = nothing materially changed AND no alerts (still send a one-liner)
    quiet = not alerts and not extremes

    def g(lbl, k):
        f = flow.get(lbl); return f.get(k) if f else None
    def v(lbl):
        f = flow.get(lbl); return f.get("value") if f else None

    L: list[str] = []
    L.append(f"📊 시장심리 브리핑 — {as_of} 아침")
    L.append("")
    L.append(f"■ 오늘 한 줄: {headline}")
    if alerts:
        L.append("")
        L.append("🚨 큰 움직임:")
        for a in alerts:
            L.append(f"   • {a}")
    L.append("")
    L.append("■ 어제까지 테이프 (FRED 일별, T+1)")
    L.append(f"   • 주식    S&P {_pct(g('S&P 500','chg5_pct'))} · 나스닥 {_pct(g('Nasdaq','chg5_pct'))} (5일)")
    L.append(f"   • 변동성  VIX {_num(v('VIX'))} ({_sgn(g('VIX','chg5'))} 5일)")
    L.append(f"   • 크레딧  HY 스프레드 {_num(v('HY spread'),2)}% ({_bp(g('HY spread','chg5_bp'))} 5일)")
    L.append(f"   • 금리/환 10Y {_num(v('UST 10Y'),2)}% ({_bp(g('UST 10Y','chg5_bp'))}) · 달러 {_pct(g('US dollar','chg5_pct'))}")
    if rates:
        L.append("")
        L.append(f"■ 금리 레짐: 커브 {rates.get('curve')} (10y-2y {rates.get('spread_10y_2y'):+}) · breakeven {rates.get('breakeven10')}%")
    L.append("")
    L.append(f"■ 포지셔닝 (CFTC, ~{lag}일 지연)")
    if extremes:
        L.append("   • 쏠림 극단: " + " · ".join(f"{p['market']}({p['extreme']})" for p in extremes))
    if vix:
        L.append(f"   • VIX {'숏(안일)' if vix['net'] < 0 else '롱(헤지)'} {vix['pctile']}%ile")
    if watch:
        L.append("")
        L.append(f"⚠️ 주목: {watch}")
    L.append("")
    L.append("데이터: CFTC · US Treasury · FRED · Finnhub")
    L.append("목표주가·리테일심리 = 미표시(라이선스)")
    text = "\n".join(L)

    snap = {
        "date": str(date.today()),
        "as_of": as_of,
        "curve": (rates or {}).get("curve"),
        "spread_10y_2y": (rates or {}).get("spread_10y_2y"),
        "extremes": {p["market"]: p["extreme"] for p in extremes},
        "flow": {lbl: (flow.get(lbl) or {}).get("value") for lbl in _ALERT},
    }

    return {
        "date": str(date.today()), "as_of": as_of, "headline": headline,
        "alerts": alerts, "watch": watch, "quiet": quiet,
        "regime": regime, "positioning": positioning, "daily_flow": flow_list,
        "rates": rates, "text": text, "_snapshot": snap,
    }


def persist(brief: dict) -> None:
    """Commit this run's snapshot so the next brief can diff against it."""
    _save_state(brief["_snapshot"])
