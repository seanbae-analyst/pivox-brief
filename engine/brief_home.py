"""Render the daily brief as research-engine-native cards (.card / teal-red palette) so it
sits at the top of the same home page as the search + featured packs — one page, one design.

Distinct from brief_html.py (which renders the standalone email/web page). This emits fragments
that inherit pack.html's existing CSS (.card, table, badges), injected by scripts/inject_home.py.
"""
from __future__ import annotations

import math

_UP, _DN, _FLAT = "#D18888", "#7AA0C8", "#94a3b8"
_UP_BG, _DN_BG = "#2a1c1f", "#17222e"
_INK, _SUB, _ACCENT, _LINE = "#e2e8f0", "#94a3b8", "#d4a558", "#334155"
_FEAR = "#cf6b6b"  # risk-off / fear (semantic, distinct from price up/down)
# mood thermometer calm → fear (cool blue → gold → warm red)
_MOOD_COL = {1: "#7AA0C8", 2: "#86a8a0", 3: "#d4a558", 4: "#cf9050", 5: "#cf6b6b"}


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _col(x):
    return _FLAT if x is None else (_UP if x > 0 else (_DN if x < 0 else _FLAT))


def _arr(x):
    return "▲" if (x or 0) > 0 else ("▼" if (x or 0) < 0 else "—")


_MONO = "font-family:var(--mono);"


def _pct_cell(x, dp=1):
    val = "n/a" if x is None else f"{x:+.{dp}f}%"
    return f'<span style="color:{_col(x)};font-weight:600;white-space:nowrap;{_MONO}">{_arr(x)} {val}</span>'


def _table(rows):
    body = ""
    for label, x in rows:
        body += (f'<tr><td style="padding:6px 0;font-size:14px;color:{_INK};">{_esc(label)}</td>'
                 f'<td style="padding:6px 0;text-align:right;font-size:14px;">{_pct_cell(x)}</td></tr>')
    return f'<table style="width:100%;border-collapse:collapse;">{body}</table>'


def _spark(vals, col, w=108, h=24):
    """Tiny SVG trendline of recent closes — area fill + end dot (web only; email strips SVG)."""
    if not vals or len(vals) < 3:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    co = [(round(j / (n - 1) * w, 1), round(h - (v - lo) / rng * (h - 6) - 3, 1)) for j, v in enumerate(vals)]
    line = " ".join(f"{x},{y}" for x, y in co)
    area = f"0,{h} " + line + f" {w},{h}"
    ex, ey = co[-1]
    return (f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'style="display:block;margin-top:8px;overflow:visible;">'
            f'<polygon points="{area}" fill="{col}" opacity="0.09"/>'
            f'<polyline points="{line}" fill="none" stroke="{col}" stroke-width="1.5" '
            f'stroke-linejoin="round" stroke-linecap="round" opacity="0.95"/>'
            f'<circle cx="{ex}" cy="{ey}" r="2.1" fill="{col}"/></svg>')


def _stat_strip(b: dict) -> str:
    """Bloomberg-style mono ticker strip of the key indices + VIX, right under the masthead."""
    sectors = b.get("sectors") or {}
    us = {i["label"]: i for i in sectors.get("us") or []}
    kr = {i["label"]: i for i in sectors.get("kr") or []}
    flow = {f["label"]: f for f in (b.get("daily_flow") or [])}
    cells = ""
    pairs = [("S&P 500", us.get("S&P 500")), ("나스닥", us.get("나스닥")),
             ("코스피", kr.get("코스피")), ("코스닥", kr.get("코스닥"))]
    for lbl, src in pairs:
        if not src or src.get("chg5_pct") is None:
            continue
        x = src["chg5_pct"]
        cells += (f'<div style="flex:1;min-width:88px;padding:10px 14px;border-right:1px solid {_LINE};">'
                  f'<div style="font:600 10px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:{_SUB};">{_esc(lbl)}</div>'
                  f'<div style="font-size:15px;font-weight:600;color:{_col(x)};{_MONO}margin-top:3px;">{_arr(x)} {x:+.1f}%</div></div>')
    vix = flow.get("VIX")
    if vix and vix.get("value") is not None:
        cells += (f'<div style="flex:1;min-width:88px;padding:10px 14px;">'
                  f'<div style="font:600 10px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:{_SUB};">VIX</div>'
                  f'<div style="font-size:15px;font-weight:600;color:{_INK};{_MONO}margin-top:3px;">{vix["value"]:.1f}</div></div>')
    if not cells:
        return ""
    return (f'<div style="display:flex;flex-wrap:wrap;border:1px solid {_LINE};border-radius:12px;'
            f'overflow:hidden;background:#111827;margin:0 0 18px;">{cells}</div>')


def _pair(a: str, b: str) -> str:
    """Two cards side-by-side on desktop (template .dgrid), stacked on mobile; solo → full width."""
    if a and b:
        return f'<div class="dgrid">{a}{b}</div>'
    return a or b or ""


def _fg_zone(s):
    return ("#7AA0C8" if s < 25 else "#86a8a0" if s < 45 else "#d4a558" if s <= 55
            else "#cf9050" if s <= 75 else "#cf6b6b")


def _polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def _gauge(score, col, w=210, h=124):
    """Semicircle dial — colored zones (fear→greed) + needle at score."""
    cx, cy, r = w / 2, h - 14, w / 2 - 16
    zones = [(0, 25, "#7AA0C8"), (25, 45, "#8aa0a8"), (45, 55, "#d4a558"),
             (55, 75, "#cf9050"), (75, 100, "#cf6b6b")]
    arcs = ""
    for lo, hi, c in zones:
        d0 = 180 * (1 - lo / 100)
        d1 = 180 * (1 - hi / 100)
        x0, y0 = _polar(cx, cy, r, d0)
        x1, y1 = _polar(cx, cy, r, d1)
        arcs += (f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {x1:.1f} {y1:.1f}" '
                 f'stroke="{c}" stroke-width="11" fill="none"/>')
    deg = 180 * (1 - score / 100)
    nx, ny = _polar(cx, cy, r - 6, deg)    # needle tip reaches the colored arc
    # NO number inside the SVG — it collided with the arc/needle. The score is shown big in
    # the label line right below the gauge instead (see _fg_card).
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block;margin:2px auto 0;">'
        f'{arcs}'
        f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="{col}" stroke-width="3" stroke-linecap="round"/>'
        f'<circle cx="{cx}" cy="{cy}" r="5" fill="{col}"/></svg>'
    )


def _trend_spark(vals, w=180, h=30):
    if not vals or len(vals) < 3:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    n = len(vals)
    pts = " ".join(f"{round(j / (n - 1) * w, 1)},{round(h - (v - lo) / rng * (h - 4) - 2, 1)}"
                   for j, v in enumerate(vals))
    return (f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'style="display:block;margin-top:2px;"><polyline points="{pts}" fill="none" '
            f'stroke="{_ACCENT}" stroke-width="1.5" stroke-linejoin="round" opacity="0.85"/></svg>')


def _components(comps):
    out = ""
    for c in comps:
        cc = _fg_zone(c["score"])
        out += (
            f'<div style="display:flex;align-items:center;gap:10px;margin:8px 0;">'
            f'<div style="flex:0 0 96px;font-size:12px;color:{_SUB};">{_esc(c["name"])}</div>'
            f'<div style="flex:1;height:6px;border-radius:3px;background:#1e293b;position:relative;">'
            f'<div style="position:absolute;left:0;top:0;bottom:0;width:{c["score"]}%;background:{cc};border-radius:3px;"></div></div>'
            f'<div style="flex:0 0 28px;text-align:right;font-size:12px;color:{_INK};{_MONO}">{c["score"]}</div></div>')
    return out


def _fg_card(fg):
    if not fg:
        return ""
    s, col = fg["score"], _fg_zone(fg["score"])
    d = fg.get("delta")
    delta = ""
    if d is not None and d != 0:
        dc = "#cf6b6b" if d > 0 else "#7AA0C8"
        delta = (f'<span style="font-size:13px;font-weight:700;color:{dc};{_MONO}">'
                 f'{"▲" if d > 0 else "▼"} 어제比 {d:+d}</span>')
    trend = ""
    if fg.get("trend"):
        trend = (f'<div style="margin-top:8px;"><div style="font-size:10px;color:{_SUB};'
                 f'{_MONO};letter-spacing:.08em;">최근 추세</div>{_trend_spark(fg["trend"])}</div>')
    return (
        f'<div class="card"><h3>공포 · 탐욕 지수</h3>'
        f'{_gauge(s, col)}'
        f'<div style="text-align:center;margin:-6px 0 2px;">'
        f'<span style="font-family:var(--serif);font-size:34px;font-weight:700;color:{col};line-height:1;">{s}</span>'
        f'<span style="font-size:17px;font-weight:700;color:{col};margin-left:8px;">{_esc(fg["label"])}</span> '
        f'<span style="font-size:11px;color:{_SUB};{_MONO}">/ 100</span>  {delta}</div>'
        f'<div style="display:flex;justify-content:space-between;font:600 10px var(--mono);color:{_SUB};letter-spacing:.06em;margin:6px 4px 14px;">'
        f'<span>극단적 공포</span><span>탐욕</span></div>'
        f'{_components(fg["components"])}'
        f'{trend}'
        f'<div style="font-size:11px;color:{_SUB};margin-top:10px;">CNN식 9요인 합성 · 무료/공식(FRED·CFTC·crypto·옵션)</div></div>'
    )


def _kr_card(kr):
    if not kr:
        return ""
    s, col = kr["score"], _fg_zone(kr["score"])
    ff = kr.get("foreign") or {}
    diverge = ""
    if ff.get("total_tril") is not None and ff.get("retail_tril") is not None:
        f_t, r_t = ff["total_tril"], ff["retail_tril"]
        fc = "#cf6b6b" if f_t > 0 else "#7AA0C8"   # 매수=빨강(KR), 매도=파랑
        rc = "#cf6b6b" if r_t > 0 else "#7AA0C8"
        tag = ("  <b style=\"color:#d4a558;\">⚖ 개미가 받치는 중</b>" if ff.get("divergence") else "")
        diverge = (
            f'<div style="margin:6px 0 4px;padding:10px 12px;background:#0f1626;border-radius:10px;'
            f'border-left:3px solid {_ACCENT};font-size:13px;color:{_INK};{_MONO}">'
            f'외국인 <span style="color:{fc};font-weight:700;">{f_t:+.1f}조</span> · '
            f'개인 <span style="color:{rc};font-weight:700;">{r_t:+.1f}조</span> '
            f'<span style="font-size:11px;color:{_SUB};">(5일, KIS 실측)</span>{tag}</div>')
    return (
        f'<div class="card"><h3>🇰🇷 한국 시장심리</h3>'
        f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:10px;">'
        f'<div style="font-family:var(--serif);font-size:38px;font-weight:700;color:{col};line-height:1;">{s}</div>'
        f'<div style="font-size:16px;font-weight:700;color:{col};">{_esc(kr["label"])}</div>'
        f'<div style="font-size:11px;color:{_SUB};{_MONO}">/ 100</div></div>'
        f'{diverge}'
        f'{_components(kr["components"])}'
        f'<div style="font-size:11px;color:{_SUB};margin-top:10px;line-height:1.5;">{_esc(kr.get("blind_spot", ""))}</div></div>'
    )


def _hot_chips(items):
    import re as _re
    cells = ""
    for i in items:
        x = i.get("chg1_pct")
        bg = _UP_BG if (x or 0) > 0 else (_DN_BG if (x or 0) < 0 else "#1e293b")
        bd = _col(x) + "33"
        # chip → deep-dive: yfinance symbol → pack query (005930.KS → 005930; US tickers as-is)
        code = _re.sub(r"[^A-Za-z0-9.\-]", "", str(i.get("symbol") or "")).split(".")[0]
        click = (f' class="hotchip" role="button" tabindex="0" onclick="openTicker(\'{code}\')"'
                 f' title="{_esc(i["label"])} 딥다이브 열기"') if code else ""
        cells += (f'<div{click} style="background:{bg};border:1px solid {bd};border-radius:10px;padding:9px 11px;">'
                  f'<div style="font-size:12px;color:{_col(x)};font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_esc(i["label"])}</div>'
                  f'<div style="font-size:19px;color:{_col(x)};font-weight:700;line-height:1.2;{_MONO}">{_arr(x)} {x:+.1f}%</div>'
                  f'{_spark(i.get("spark"), _col(x))}</div>')
    return (f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(116px,1fr));gap:8px;">{cells}</div>')


def render_home_cards(b: dict) -> str:
    risk = b.get("headline", "")
    rcol = _FEAR if "회피" in risk else (_UP if "선호" in risk else _SUB)
    rbg = "#2a1a1a" if "회피" in risk else (_UP_BG if "선호" in risk else "#1e293b")
    P = []

    # ── masthead — compact dashboard header (dated kicker + one-line serif tagline) ──
    P.append(
        f'<div style="padding:2px 2px 14px;">'
        f'<div style="font:600 11px var(--mono);letter-spacing:.2em;text-transform:uppercase;color:{_ACCENT};">'
        f'시장심리 브리핑 · {_esc(b.get("as_of"))} 아침</div>'
        f'<div style="font-family:var(--serif);font-weight:600;font-size:21px;color:{_INK};margin-top:6px;line-height:1.25;letter-spacing:.01em;">'
        f'Market psychology, distilled every morning.</div>'
        f'</div>'
    )
    _ms = b.get("market_status") or {}
    if _ms.get("banner"):
        P.append(
            f'<div style="margin:0 2px 16px;padding:9px 13px;background:#1e293b;border-radius:9px;'
            f'border-left:3px solid {_ACCENT};font-size:13px;color:{_INK};">📅 {_esc(_ms["banner"])}</div>'
        )
    P.append(_stat_strip(b))

    # ── 오늘의 시장 (mood + headline + 쉬운 풀이 + 그래서 뭐) ──
    m = b.get("mood")
    P.append('<div class="card"><h3>오늘의 시장</h3>')
    if b.get("guide") and m:
        col = _MOOD_COL.get(m["level"], _SUB)
        pos = round((m["level"] - 1) / 4 * 100)
        bar = (
            f'<div style="position:relative;height:8px;border-radius:5px;margin:9px 0 16px;'
            f'background:linear-gradient(90deg,#7AA0C8,#86a8a0,#d4a558,#cf9050,#cf6b6b);">'
            f'<div style="position:absolute;top:-4px;left:{pos}%;width:16px;height:16px;border-radius:50%;'
            f'background:{col};border:3px solid #111827;transform:translateX(-50%);box-shadow:0 0 0 1px {col}cc;"></div></div>'
        )
        P.append(f'<div style="font-size:15px;font-weight:700;color:{col};margin-bottom:2px;">'
                 f'{m["emoji"]} 시장 기분: {_esc(m["label"])} '
                 f'<span style="font-weight:500;color:{_SUB};font-size:12px;">5단계 중 {m["level"]} · {_esc(m["note"])}</span></div>'
                 f'{bar}')
    P.append(f'<div style="display:inline-block;background:{rbg};color:{rcol};font-weight:700;'
             f'font-size:18px;padding:8px 14px;border-radius:8px;letter-spacing:-.2px;border:1px solid {rcol}44;">{_esc(risk)}</div>')
    if b.get("plain"):
        P.append(f'<p style="font-size:14px;color:{_INK};margin:10px 0 0;line-height:1.55;">{_esc(b["plain"])}</p>')
    if b.get("guide") and b.get("sowhat"):
        P.append(f'<p style="font-size:13px;color:{_INK};margin:6px 0 0;line-height:1.5;">'
                 f'<b style="color:{rcol};">그래서 뭐?</b> {_esc(b["sowhat"])}</p>')
    P.append('</div>')

    # ── 공포·탐욕 지수 + 한국 시장심리 — side-by-side on desktop (dashboard grid) ──
    P.append(_pair(_fg_card(b.get("fear_greed")), _kr_card(b.get("korea"))))

    # ── 🔥 핫 종목 (full width; chips open the ticker deep-dive) ──
    us_hot, kr_hot = b.get("us_hot") or [], b.get("kr_hot") or []
    if us_hot or kr_hot:
        P.append('<div class="card"><h3>핫 종목 · 오늘 제일 많이 움직인</h3>')
        P.append(f'<p style="font-size:11.5px;color:{_SUB};margin:-8px 0 10px;">칩을 누르면 그 종목의 공시 기반 딥다이브로 넘어가요</p>')
        if us_hot:
            P.append(f'<div style="font-size:12px;font-weight:700;color:{_SUB};margin:0 0 6px;">🇺🇸 미국</div>{_hot_chips(us_hot)}')
        if kr_hot:
            P.append(f'<div style="font-size:12px;font-weight:700;color:{_SUB};margin:12px 0 6px;">🇰🇷 한국</div>{_hot_chips(kr_hot)}')
        P.append('</div>')

    # ── 미국장 / 한국장 — side-by-side on desktop ──
    sectors = b.get("sectors") or {}
    us, kr = sectors.get("us") or [], sectors.get("kr") or []
    us_idx = [(i["label"], i["chg5_pct"]) for i in us if i["group"] == "지수"]
    us_sec = [(i["label"], i["chg5_pct"]) for i in us if i["group"] == "섹터"]
    kr_idx = [(i["label"], i["chg5_pct"]) for i in kr if i["group"] == "지수"]
    us_card = kr_card = ""
    if us_idx or us_sec:
        us_card = '<div class="card"><h3>🇺🇸 미국장 · 5일 변화</h3>' + _table(us_idx + us_sec)
        if b.get("us_rotation"):
            us_card += f'<p style="font-size:13px;color:{_INK};margin:10px 0 0;padding-left:10px;border-left:3px solid {_ACCENT};line-height:1.5;"><b>한눈에</b> {_esc(b["us_rotation"])}</p>'
        us_card += '</div>'
    if kr_idx:
        kr_card = '<div class="card"><h3>🇰🇷 한국장 · 5일 변화</h3>' + _table(kr_idx)
        if b.get("kr_read"):
            kr_card += f'<p style="font-size:13px;color:{_INK};margin:10px 0 0;padding-left:10px;border-left:3px solid {_ACCENT};line-height:1.5;"><b>한눈에</b> {_esc(b["kr_read"])}</p>'
        kr_card += '</div>'
    P.append(_pair(us_card, kr_card))

    # ── 📖 배우기 (초보) ──
    if b.get("teach"):
        tod = b.get("term_of_day")
        P.append('<div class="card"><h3>배우기</h3>')
        if tod:
            ana = f'<div style="font-size:13px;color:{_SUB};margin-top:5px;">비유: {_esc(tod["analogy"])}</div>' if tod.get("analogy") else ""
            P.append(f'<div style="background:{_UP_BG};border-radius:10px;padding:12px 14px;">'
                     f'<div style="font-size:12px;font-weight:700;color:{_ACCENT};">오늘의 용어</div>'
                     f'<div style="font-size:16px;font-weight:800;color:{_INK};margin-top:2px;">{_esc(tod["term"])}</div>'
                     f'<div style="font-size:13px;color:{_INK};margin-top:4px;line-height:1.55;">{_esc(tod["long"])}</div>{ana}</div>')
        if b.get("glossary"):
            chips = "".join(
                f'<span style="display:inline-block;background:#1e293b;border-radius:8px;padding:5px 10px;'
                f'margin:6px 6px 0 0;font-size:12px;color:{_INK};"><b>{_esc(x["term"])}</b> {_esc(x["gloss"])}</span>'
                for x in b["glossary"])
            P.append(f'<div style="line-height:1.9;margin-top:4px;">{chips}</div>')
        P.append('</div>')

    src = f'<div style="font-size:11px;color:{_SUB};margin:0 2px 8px;font-family:var(--mono);">DATA · yfinance · CFTC · FRED · US Treasury · 정보 제공용, 투자자문 아님</div>'
    return f'<div style="margin-bottom:8px;">{"".join(P)}</div>{src}'
