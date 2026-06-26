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
from engine.sectors import build_sectors

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


_PLAIN = {
    "위험선호": "투자자들이 자신감 있게 위험을 감수하는 분위기예요 (주식에 돈이 들어옴).",
    "위험회피": "투자자들이 불안해서 주식보다 안전한 곳으로 돈을 옮기는 분위기예요 (몸 사리는 중).",
    "혼조": "뚜렷한 방향 없이 위아래로 엇갈리는 분위기예요.",
}


def _plain_headline(headline: str) -> str:
    for k, v in _PLAIN.items():
        if headline.startswith(k):
            return v
    return ""


def _arrow(x) -> str:
    if x is None:
        return "▪"
    return "🔺" if x > 0 else ("🔻" if x < 0 else "▪")


def _move_row(items: list[dict]) -> str:
    return "  ".join(f"{_arrow(i['chg5_pct'])}{i['label']} {i['chg5_pct']:+.1f}%" for i in items)


def _us_rotation(us: list[dict]) -> str | None:
    secs = [i for i in us if i["group"] == "섹터"]
    if not secs:
        return None
    top = max(secs, key=lambda i: i["chg5_pct"])
    bot = min(secs, key=lambda i: i["chg5_pct"])
    if top["chg5_pct"] > 0 and bot["chg5_pct"] < 0:
        return f"{top['label']}는 오르고 {bot['label']}는 빠짐 — 돈이 {top['label']} 쪽으로 쏠리는 흐름."
    if top["chg5_pct"] <= 0:
        return f"섹터 전반 약세 (제일 부진: {bot['label']} {bot['chg5_pct']:+.1f}%)."
    return f"섹터 전반 강세 (제일 강세: {top['label']} {top['chg5_pct']:+.1f}%)."


def _kr_read(kr: list[dict], kr_hot: list[dict] | None = None) -> str | None:
    by = {i["label"]: i for i in kr}
    ks, kq = by.get("코스피"), by.get("코스닥")
    if not (ks and kq):
        return None
    worst = min(kr_hot, key=lambda i: i["chg1_pct"], default=None) if kr_hot else None
    if ks["chg5_pct"] < 0 and kq["chg5_pct"] < 0:
        t = f"한국 증시 전반 약세 (코스피 {ks['chg5_pct']:+.1f}%, 코스닥 {kq['chg5_pct']:+.1f}%)."
        if worst and worst["chg1_pct"] < -3:
            t += f" 오늘 특히 {worst['label']}({worst['chg1_pct']:+.1f}%)이 많이 빠짐."
        return t
    if ks["chg5_pct"] > 0 and kq["chg5_pct"] > 0:
        return f"한국 증시 전반 강세 (코스피 {ks['chg5_pct']:+.1f}%, 코스닥 {kq['chg5_pct']:+.1f}%)."
    return f"코스피 {ks['chg5_pct']:+.1f}%, 코스닥 {kq['chg5_pct']:+.1f}% — 방향이 엇갈림."


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
    sectors = build_sectors()
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

    us = (sectors or {}).get("us") or []
    kr = (sectors or {}).get("kr") or []
    us_hot = (sectors or {}).get("us_hot") or []
    kr_hot = (sectors or {}).get("kr_hot") or []
    us_idx = [i for i in us if i["group"] == "지수"]
    us_sec = [i for i in us if i["group"] == "섹터"]
    kr_idx = [i for i in kr if i["group"] == "지수"]
    kr_fx = next((i for i in kr if i["group"] == "환율"), None)

    def hot_row(items):
        return "  ".join(f"{_arrow(i['chg1_pct'])}{i['label']} {i['chg1_pct']:+.1f}%" for i in items)

    L: list[str] = []
    L.append(f"📊 시장심리 브리핑 — {as_of} 아침")
    L.append("")
    L.append(f"오늘 한 줄: {headline}")
    plain = _plain_headline(headline)
    if plain:
        L.append(f"쉬운 풀이: {plain}")
    if alerts:
        L.append("")
        L.append("🚨 큰 움직임:")
        for a in alerts:
            L.append(f"   • {a}")

    # ── 🔥 핫 종목 (오늘 제일 많이 움직인) ──
    if us_hot or kr_hot:
        L.append("")
        L.append("━━ 🔥 핫 종목 (오늘 제일 많이 움직인) ━━")
        if us_hot:
            L.append("🇺🇸 " + hot_row(us_hot))
        if kr_hot:
            L.append("🇰🇷 " + hot_row(kr_hot))

    # ── 🇺🇸 미국장 ──
    L.append("")
    L.append("━━ 🇺🇸 미국장 (어제 마감 기준, 괄호는 5일 변화) ━━")
    if us_idx:
        L.append("지수   " + _move_row(us_idx))
    if us_sec:
        L.append("섹터   " + _move_row(us_sec))
    rot = _us_rotation(us)
    if rot:
        L.append(f"한눈에: {rot}")
    if not us:  # yfinance down → fall back to the FRED tape so the section isn't empty
        L.append(f"지수   S&P {_pct(g('S&P 500','chg5_pct'))} · 나스닥 {_pct(g('Nasdaq','chg5_pct'))} (5일)")

    # ── 🇰🇷 한국장 ──
    L.append("")
    L.append("━━ 🇰🇷 한국장 (오늘 마감 기준, 괄호는 5일 변화) ━━")
    if kr_idx:
        L.append("지수   " + _move_row(kr_idx))
    if kr_fx:
        won = "원화 약세(달러 비쌈)" if (kr_fx["chg5_pct"] or 0) > 0 else "원화 강세(달러 쌈)"
        L.append(f"환율   원/달러 {kr_fx['last']:,.0f}원 ({kr_fx['chg5_pct']:+.1f}% → {won})")
    kread = _kr_read(kr, kr_hot)
    if kread:
        L.append(f"한눈에: {kread}")
    if not kr:
        L.append("(한국장 데이터 일시 불가 — yfinance 응답 없음)")

    if watch:
        L.append("")
        L.append(f"⚠️ 주목: {watch}")

    # ── 심화(전문) — 어려운 건 맨 아래로 ──
    L.append("")
    L.append("━━ 심화 (관심 있을 때만) ━━")
    L.append(f"· 변동성·신용: VIX {_num(v('VIX'))}({_sgn(g('VIX','chg5'))} 5일) · HY 스프레드 {_num(v('HY spread'),2)}%({_bp(g('HY spread','chg5_bp'))} 5일, 벌어질수록 신용 불안)")
    if rates:
        L.append(f"· 금리: 美 10년 {_num(v('UST 10Y'),2)}% · 커브 {rates.get('curve')}(정상이면 경기침체 신호 아님)")
    if extremes:
        L.append("· 선물 쏠림(반전 주의): " + " · ".join(f"{p['market']}({p['extreme']})" for p in extremes) + f" — CFTC, ~{lag}일 지연")

    L.append("")
    L.append("데이터: yfinance(지수·섹터·종목) · CFTC · FRED · US Treasury")
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

    brief = {
        "date": str(date.today()), "as_of": as_of, "headline": headline,
        "plain": plain, "alerts": alerts, "watch": watch, "quiet": quiet,
        "regime": regime, "positioning": positioning, "extremes": extremes,
        "daily_flow": flow_list, "rates": rates, "lag": lag,
        "sectors": sectors, "us_hot": us_hot, "kr_hot": kr_hot,
        "us_rotation": rot, "kr_read": kread,
        "text": text, "_snapshot": snap,
    }
    from engine.brief_html import render_html
    brief["html"] = render_html(brief)
    return brief


def persist(brief: dict) -> None:
    """Commit this run's snapshot so the next brief can diff against it."""
    _save_state(brief["_snapshot"])
