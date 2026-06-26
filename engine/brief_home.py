"""Render the daily brief as research-engine-native cards (.card / teal-red palette) so it
sits at the top of the same home page as the search + featured packs — one page, one design.

Distinct from brief_html.py (which renders the standalone email/web page). This emits fragments
that inherit pack.html's existing CSS (.card, table, badges), injected by scripts/inject_home.py.
"""
from __future__ import annotations

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
    return f'<span style="color:{_col(x)};font-weight:600;white-space:nowrap;{_MONO}">{_arr(x)} {x:+.{dp}f}%</span>'


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


def _hot_chips(items):
    cells = ""
    for i in items:
        x = i.get("chg1_pct")
        bg = _UP_BG if (x or 0) > 0 else (_DN_BG if (x or 0) < 0 else "#1e293b")
        bd = _col(x) + "33"
        cells += (f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:9px 11px;">'
                  f'<div style="font-size:12px;color:{_col(x)};font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_esc(i["label"])}</div>'
                  f'<div style="font-size:19px;color:{_col(x)};font-weight:700;line-height:1.2;{_MONO}">{_arr(x)} {x:+.1f}%</div>'
                  f'{_spark(i.get("spark"), _col(x))}</div>')
    return (f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(116px,1fr));gap:8px;">{cells}</div>')


def render_home_cards(b: dict) -> str:
    risk = b.get("headline", "")
    rcol = _FEAR if "회피" in risk else (_UP if "선호" in risk else _SUB)
    rbg = "#2a1a1a" if "회피" in risk else (_UP_BG if "선호" in risk else "#1e293b")
    P = []

    # ── masthead — editorial Playfair tagline + dated kicker ──
    P.append(
        f'<div style="padding:4px 2px 20px;">'
        f'<div style="font:600 11px var(--mono);letter-spacing:.2em;text-transform:uppercase;color:{_ACCENT};">'
        f'시장심리 브리핑 · {_esc(b.get("as_of"))} 아침</div>'
        f'<div style="font-family:var(--serif);font-weight:600;font-size:31px;color:{_INK};margin-top:10px;line-height:1.18;letter-spacing:.01em;">'
        f'Market psychology,<br>distilled every morning.</div>'
        f'<div style="height:2px;width:48px;background:{_ACCENT};opacity:.8;margin-top:16px;border-radius:1px;"></div>'
        f'</div>'
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

    # ── 🔥 핫 종목 ──
    us_hot, kr_hot = b.get("us_hot") or [], b.get("kr_hot") or []
    if us_hot or kr_hot:
        P.append('<div class="card"><h3>핫 종목 · 오늘 제일 많이 움직인</h3>')
        if us_hot:
            P.append(f'<div style="font-size:12px;font-weight:700;color:{_SUB};margin:0 0 6px;">🇺🇸 미국</div>{_hot_chips(us_hot)}')
        if kr_hot:
            P.append(f'<div style="font-size:12px;font-weight:700;color:{_SUB};margin:12px 0 6px;">🇰🇷 한국</div>{_hot_chips(kr_hot)}')
        P.append('</div>')

    # ── 미국장 / 한국장 ──
    sectors = b.get("sectors") or {}
    us, kr = sectors.get("us") or [], sectors.get("kr") or []
    us_idx = [(i["label"], i["chg5_pct"]) for i in us if i["group"] == "지수"]
    us_sec = [(i["label"], i["chg5_pct"]) for i in us if i["group"] == "섹터"]
    kr_idx = [(i["label"], i["chg5_pct"]) for i in kr if i["group"] == "지수"]
    if us_idx or us_sec:
        P.append('<div class="card"><h3>🇺🇸 미국장 · 5일 변화</h3>')
        P.append(_table(us_idx + us_sec))
        if b.get("us_rotation"):
            P.append(f'<p style="font-size:13px;color:{_INK};margin:10px 0 0;padding-left:10px;border-left:3px solid {_ACCENT};line-height:1.5;"><b>한눈에</b> {_esc(b["us_rotation"])}</p>')
        P.append('</div>')
    if kr_idx:
        P.append('<div class="card"><h3>🇰🇷 한국장 · 5일 변화</h3>')
        P.append(_table(kr_idx))
        if b.get("kr_read"):
            P.append(f'<p style="font-size:13px;color:{_INK};margin:10px 0 0;padding-left:10px;border-left:3px solid {_ACCENT};line-height:1.5;"><b>한눈에</b> {_esc(b["kr_read"])}</p>')
        P.append('</div>')

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

    src = f'<div style="font-size:11px;color:{_SUB};margin:0 2px 16px;font-family:var(--mono);">DATA · yfinance · CFTC · FRED · US Treasury · 정보 제공용, 투자자문 아님</div>'
    divider = (
        f'<div style="display:flex;align-items:center;gap:12px;margin:4px 2px 20px;">'
        f'<div style="flex:1;height:1px;background:{_LINE};"></div>'
        f'<div style="font:600 10px var(--mono);letter-spacing:.18em;text-transform:uppercase;color:{_ACCENT};">종목 깊이 보기 ↓</div>'
        f'<div style="flex:1;height:1px;background:{_LINE};"></div></div>'
    )
    return f'<div style="margin-bottom:8px;">{"".join(P)}</div>{src}{divider}'
