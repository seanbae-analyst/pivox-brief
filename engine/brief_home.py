"""Render the daily brief as research-engine-native cards (.card / teal-red palette) so it
sits at the top of the same home page as the search + featured packs — one page, one design.

Distinct from brief_html.py (which renders the standalone email/web page). This emits fragments
that inherit pack.html's existing CSS (.card, table, badges), injected by scripts/inject_home.py.
"""
from __future__ import annotations

_UP, _DN, _FLAT = "#5ec08a", "#e26d60", "#8b919b"
_UP_BG, _DN_BG = "#15241d", "#261718"
_INK, _SUB, _ACCENT = "#ECEAE3", "#8b919b", "#c6a063"
_MOOD_COL = {1: "#5ec08a", 2: "#8fb56a", 3: "#c6a063", 4: "#d6a44f", 5: "#e26d60"}


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


def _hot_chips(items):
    cells = ""
    for i in items:
        x = i.get("chg1_pct")
        bg = _UP_BG if (x or 0) > 0 else (_DN_BG if (x or 0) < 0 else "#161a20")
        cells += (f'<div style="background:{bg};border-radius:10px;padding:9px 11px;">'
                  f'<div style="font-size:12px;color:{_col(x)};font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_esc(i["label"])}</div>'
                  f'<div style="font-size:19px;color:{_col(x)};font-weight:700;line-height:1.2;{_MONO}">{_arr(x)} {x:+.1f}%</div></div>')
    return (f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(116px,1fr));gap:8px;">{cells}</div>')


def render_home_cards(b: dict) -> str:
    risk = b.get("headline", "")
    rcol = _DN if "회피" in risk else (_UP if "선호" in risk else _SUB)
    rbg = _DN_BG if "회피" in risk else (_UP_BG if "선호" in risk else "#161a20")
    P = []

    # ── 오늘의 시장 (mood + headline + 쉬운 풀이 + 그래서 뭐) ──
    m = b.get("mood")
    P.append('<div class="card">')
    if b.get("guide") and m:
        col = _MOOD_COL.get(m["level"], _SUB)
        dots = "".join(
            f'<span style="display:inline-block;width:26px;height:7px;border-radius:3px;margin-right:3px;'
            f'background:{col if i <= m["level"] else "#1f2329"};"></span>' for i in range(1, 6))
        P.append(f'<div style="font-size:15px;font-weight:800;color:{col};margin-bottom:2px;">'
                 f'{m["emoji"]} 시장 기분: {_esc(m["label"])} '
                 f'<span style="font-weight:500;color:{_SUB};font-size:12px;">5단계 중 {m["level"]} · {_esc(m["note"])}</span></div>'
                 f'<div style="margin:4px 0 12px;">{dots}</div>')
    P.append(f'<div style="display:inline-block;background:{rbg};color:{rcol};font-weight:800;'
             f'font-size:18px;padding:7px 13px;border-radius:999px;letter-spacing:-.3px;">{_esc(risk)}</div>')
    if b.get("plain"):
        P.append(f'<p style="font-size:14px;color:{_INK};margin:10px 0 0;line-height:1.55;">{_esc(b["plain"])}</p>')
    if b.get("guide") and b.get("sowhat"):
        P.append(f'<p style="font-size:13px;color:{_INK};margin:6px 0 0;line-height:1.5;">'
                 f'<b style="color:{rcol};">그래서 뭐?</b> {_esc(b["sowhat"])}</p>')
    P.append('</div>')

    # ── 🔥 핫 종목 ──
    us_hot, kr_hot = b.get("us_hot") or [], b.get("kr_hot") or []
    if us_hot or kr_hot:
        P.append('<div class="card"><h3>🔥 핫 종목 · 오늘 제일 많이 움직인</h3>')
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
        P.append('<div class="card"><h3>📖 배우기</h3>')
        if tod:
            ana = f'<div style="font-size:13px;color:{_SUB};margin-top:5px;">비유: {_esc(tod["analogy"])}</div>' if tod.get("analogy") else ""
            P.append(f'<div style="background:{_UP_BG};border-radius:10px;padding:12px 14px;">'
                     f'<div style="font-size:12px;font-weight:700;color:{_ACCENT};">오늘의 용어</div>'
                     f'<div style="font-size:16px;font-weight:800;color:{_INK};margin-top:2px;">{_esc(tod["term"])}</div>'
                     f'<div style="font-size:13px;color:{_INK};margin-top:4px;line-height:1.55;">{_esc(tod["long"])}</div>{ana}</div>')
        if b.get("glossary"):
            chips = "".join(
                f'<span style="display:inline-block;background:#161a20;border-radius:8px;padding:5px 10px;'
                f'margin:6px 6px 0 0;font-size:12px;color:{_INK};"><b>{_esc(x["term"])}</b> {_esc(x["gloss"])}</span>'
                for x in b["glossary"])
            P.append(f'<div style="line-height:1.9;margin-top:4px;">{chips}</div>')
        P.append('</div>')

    note = f'<div style="font-size:12px;color:{_SUB};margin:2px 0 18px;">아래에서 개별 종목도 검색해 보세요 ↓ · 데이터: yfinance · CFTC · FRED · 정보 제공용</div>'
    return f'<div style="margin-bottom:8px;">{"".join(P)}</div>{note}'
