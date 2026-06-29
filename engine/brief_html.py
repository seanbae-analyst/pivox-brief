"""HTML email renderer for the morning brief — the 'make it POP' layer.

Email clients (Gmail especially) are hostile: no <style> reliability, no flexbox, no JS. So
this is table-based with INLINE styles only, single column, max-width 600, system fonts.
Colors follow the Korean convention (상승=빨강, 하락=파랑) since the reader is Korean and the
brief leads with the KR market; arrows (▲▼) carry direction independent of color. The 🔥 hot
movers are the visual hero — big tinted chips with 22px numbers — since that's what gets opened.
"""
from __future__ import annotations

# Vantablack + Bronze: dark terminal, gold accent, up=green / down=red
_UP, _DN, _FLAT = "#D18888", "#7AA0C8", "#94a3b8"
_UP_BG, _DN_BG, _FLAT_BG = "#2a1c1f", "#17222e", "#1e293b"
_INK, _SUB, _LINE, _BG, _CARD = "#e2e8f0", "#94a3b8", "#334155", "#0a0e17", "#111827"
_ACCENT = "#d4a558"


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _col(x) -> str:
    if x is None:
        return _FLAT
    return _UP if x > 0 else (_DN if x < 0 else _FLAT)


def _tint(x) -> str:
    if x is None:
        return _FLAT_BG
    return _UP_BG if x > 0 else (_DN_BG if x < 0 else _FLAT_BG)


def _arr(x) -> str:
    return "▲" if (x or 0) > 0 else ("▼" if (x or 0) < 0 else "—")


def _hot_grid(items: list[dict]) -> str:
    """2-column grid of big tinted chips — the hero. Uses chg1_pct (today's move)."""
    cells = []
    for i in items:
        x = i.get("chg1_pct")
        cells.append(
            f'<td width="50%" valign="top" style="padding:4px;">'
            f'<div style="background:{_tint(x)};border-radius:12px;padding:11px 13px;">'
            f'<div style="font-size:13px;color:{_col(x)};font-weight:600;white-space:nowrap;overflow:hidden;">{_esc(i["label"])}</div>'
            f'<div style="font-size:23px;color:{_col(x)};font-weight:800;line-height:1.15;letter-spacing:-.3px;white-space:nowrap;">{_arr(x)} {x:+.1f}%</div>'
            f'</div></td>'
        )
    rows = ""
    for k in range(0, len(cells), 2):
        pair = cells[k:k + 2]
        if len(pair) == 1:
            pair.append('<td width="50%" style="padding:4px;"></td>')
        rows += f"<tr>{''.join(pair)}</tr>"
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;">{rows}</table>')


def _rows(items: list[dict]) -> str:
    out = []
    for i in items:
        x = i.get("chg5_pct")
        val = "n/a" if x is None else f"{x:+.1f}%"
        out.append(
            f'<tr>'
            f'<td style="padding:7px 0;font-size:15px;color:{_INK};white-space:nowrap;">{_esc(i["label"])}</td>'
            f'<td style="padding:7px 0;text-align:right;font-size:16px;font-weight:800;'
            f'color:{_col(x)};white-space:nowrap;letter-spacing:-.2px;">{_arr(x)} {val}</td>'
            f'</tr>'
        )
    return "".join(out)


def _card(flag: str, title: str, sub: str, body: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:separate;background:{_CARD};border:1px solid {_LINE};'
        f'border-radius:16px;margin:0 0 14px;"><tr><td style="padding:16px 18px;">'
        f'<div style="font-size:16px;font-weight:800;color:{_INK};letter-spacing:-.2px;">{flag} {_esc(title)}'
        f'<span style="font-weight:500;color:{_SUB};font-size:12px;">  {_esc(sub)}</span></div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:6px;">{body}</table>'
        f'</td></tr></table>'
    )


def _section_title(text: str) -> str:
    return (f'<div style="font-size:17px;font-weight:800;color:{_INK};letter-spacing:-.3px;'
            f'margin:4px 2px 8px;">{text}</div>')


_FEAR = "#cf6b6b"
_MOOD_COL = {1: "#7AA0C8", 2: "#86a8a0", 3: "#d4a558", 4: "#cf9050", 5: "#cf6b6b"}


def _thermo(m: dict) -> str:
    lv, col = m["level"], _MOOD_COL.get(m["level"], _SUB)
    segs = ""
    for i in range(1, 6):
        c = col if i <= lv else "#334155"
        segs += (f'<td height="9" style="background:{c};font-size:0;line-height:0;border-radius:3px;">&nbsp;</td>'
                 f'<td width="4" style="font-size:0;line-height:0;">&nbsp;</td>')
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:10px;"><tr>'
        f'<td width="34" style="font-size:26px;vertical-align:middle;">{m["emoji"]}</td>'
        f'<td style="vertical-align:middle;">'
        f'<div style="font-size:14px;font-weight:800;color:{col};">시장 기분: {_esc(m["label"])} '
        f'<span style="font-weight:500;color:{_SUB};font-size:12px;">5단계 중 {lv} · {_esc(m["note"])}</span></div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:5px;max-width:240px;"><tr>{segs}</tr></table>'
        f'</td></tr></table>'
    )


def _callout(text: str, color: str, bg: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:separate;margin:2px 0 12px;"><tr>'
        f'<td style="padding:11px 14px;background:{bg};border-left:4px solid {color};'
        f'border-radius:8px;font-size:14px;color:{_INK};line-height:1.5;">{text}</td>'
        f'</tr></table>'
    )


def _fg_zone(s):
    return ("#7AA0C8" if s < 25 else "#86a8a0" if s < 45 else "#d4a558" if s <= 55
            else "#cf9050" if s <= 75 else "#cf6b6b")


def _fg_block(fg) -> str:
    if not fg:
        return ""
    s, col = fg["score"], _fg_zone(fg["score"])
    rows = (f'<tr><td colspan="3" style="padding:2px 0 12px;">'
            f'<span style="font-size:36px;font-weight:800;color:{col};">{s}</span>'
            f'<span style="font-size:16px;font-weight:700;color:{col};"> {_esc(fg["label"])}</span>'
            f'<span style="font-size:12px;color:{_SUB};"> / 100</span></td></tr>')
    for c in fg["components"]:
        cc, w = _fg_zone(c["score"]), int(c["score"])
        rows += (
            f'<tr><td style="padding:5px 0;font-size:13px;color:{_SUB};white-space:nowrap;">{_esc(c["name"])}</td>'
            f'<td style="padding:5px 10px;width:99%;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>'
            f'<td width="{w}%" height="6" style="background:{cc};font-size:0;line-height:0;border-radius:3px;">&nbsp;</td>'
            f'<td height="6" style="font-size:0;line-height:0;background:#1e293b;border-radius:3px;">&nbsp;</td></tr></table></td>'
            f'<td style="padding:5px 0;text-align:right;font-size:13px;color:{_INK};">{c["score"]}</td></tr>')
    return _card("😱", "공포·탐욕 지수", "CNN식 6요인 합성 · 무료/공식 데이터", rows)


def render_html(b: dict) -> str:
    sectors = b.get("sectors") or {}
    us = sectors.get("us") or []
    kr = sectors.get("kr") or []
    us_hot = b.get("us_hot") or []
    kr_hot = b.get("kr_hot") or []
    us_idx = [i for i in us if i["group"] == "지수"]
    us_sec = [i for i in us if i["group"] == "섹터"]
    kr_idx = [i for i in kr if i["group"] == "지수"]
    kr_fx = next((i for i in kr if i["group"] == "환율"), None)

    risk = b.get("headline", "")
    band = (_FEAR, "#2a1a1a") if "회피" in risk else ((_UP, _UP_BG) if "선호" in risk else (_SUB, _FLAT_BG))

    P = []
    P.append(f'<div style="background:{_BG};padding:18px 12px;">')
    P.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
             f'style="max-width:600px;margin:0 auto;border-collapse:collapse;font-family:'
             f'-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;">')
    P.append('<tr><td>')

    # header
    P.append(f'<div style="font-size:22px;font-weight:800;color:{_INK};letter-spacing:-.5px;">'
             f'📊 시장심리 브리핑</div>'
             f'<div style="font-size:12px;color:{_SUB};margin:2px 0 12px;">{_esc(b.get("as_of"))} · 아침</div>')
    _ms = b.get("market_status") or {}
    if _ms.get("banner"):
        P.append(f'<div style="margin:0 0 14px;padding:9px 13px;background:#1e293b;border-radius:9px;'
                 f'border-left:3px solid {_DN};font-size:13px;color:{_INK};">📅 {_esc(_ms["banner"])}</div>')

    # hero band — headline + plain + (beginner) so-what + thermometer
    guide = b.get("guide")
    hero = f'<div style="font-size:21px;font-weight:800;color:{band[0]};line-height:1.3;letter-spacing:-.4px;">{_esc(risk)}</div>'
    if b.get("plain"):
        hero += f'<div style="font-size:14px;color:{_INK};margin-top:7px;line-height:1.55;">{_esc(b["plain"])}</div>'
    if guide and b.get("sowhat"):
        hero += (f'<div style="font-size:13px;color:{_INK};margin-top:8px;line-height:1.5;">'
                 f'<b style="color:{band[0]};">그래서 뭐?</b>  {_esc(b["sowhat"])}</div>')
    if guide and b.get("mood"):
        hero += _thermo(b["mood"])
    P.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
             f'style="border-collapse:separate;margin:0 0 16px;"><tr><td '
             f'style="background:{band[1]};border-radius:14px;padding:16px 18px;">{hero}</td></tr></table>')

    # alerts
    if b.get("alerts"):
        items = "".join(f'<div style="margin:3px 0;">• {_esc(a)}</div>' for a in b["alerts"])
        P.append(_callout(f'<b>🚨 큰 움직임</b><div style="margin-top:4px;">{items}</div>', _DN, _DN_BG))

    # 공포·탐욕 지수
    P.append(_fg_block(b.get("fear_greed")))

    # 🔥 HOT — the hero
    if us_hot or kr_hot:
        P.append(_section_title("🔥 핫 종목 <span style=\"font-size:12px;font-weight:500;color:#5b6470;\">오늘 제일 많이 움직인</span>"))
        if us_hot:
            P.append(f'<div style="font-size:13px;font-weight:700;color:{_SUB};margin:6px 2px 2px;">🇺🇸 미국</div>')
            P.append(_hot_grid(us_hot))
        if kr_hot:
            P.append(f'<div style="font-size:13px;font-weight:700;color:{_SUB};margin:10px 2px 2px;">🇰🇷 한국</div>')
            P.append(_hot_grid(kr_hot))
        P.append('<div style="height:14px;"></div>')

    # US card
    body = _rows(us_idx)
    if us_sec:
        if body:
            body += f'<tr><td colspan="2" style="border-top:1px solid {_LINE};padding-top:2px;"></td></tr>'
        body += _rows(us_sec)
    if body:
        P.append(_card("🇺🇸", "미국장", "어제 마감 · 5일 변화", body))
        if b.get("us_rotation"):
            P.append(_callout(f'<b>한눈에</b>  {_esc(b["us_rotation"])}', band[0], "#1e293b"))

    # KR card
    body = _rows(kr_idx)
    if kr_fx:
        won = "원화 약세" if (kr_fx["chg5_pct"] or 0) > 0 else "원화 강세"
        body += (f'<tr><td style="padding:7px 0;font-size:15px;color:{_INK};">원/달러</td>'
                 f'<td style="padding:7px 0;text-align:right;font-size:15px;font-weight:800;color:{_col(kr_fx["chg5_pct"])};white-space:nowrap;">'
                 f'{kr_fx["last"]:,.0f}원 · {won}</td></tr>')
    if body:
        P.append(_card("🇰🇷", "한국장", "오늘 마감 · 5일 변화", body))
        if b.get("kr_read"):
            P.append(_callout(f'<b>한눈에</b>  {_esc(b["kr_read"])}', band[0], "#1e293b"))

    # watch
    if b.get("watch"):
        P.append(_callout(f'<b>⚠️ 주목</b>  {_esc(b["watch"])}', "#d4a558", "#241d0e"))

    # 📖 배우기 (초보 모드) — 오늘의 용어 + 용어 풀이
    if b.get("teach"):
        P.append(_section_title("📖 배우기"))
        tod = b.get("term_of_day")
        if tod:
            ana = f'<div style="font-size:13px;color:{_SUB};margin-top:5px;line-height:1.5;">비유: {_esc(tod["analogy"])}</div>' if tod.get("analogy") else ""
            P.append(
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="border-collapse:separate;margin:0 0 10px;"><tr><td '
                f'style="background:{_UP_BG};border-radius:12px;padding:13px 15px;">'
                f'<div style="font-size:12px;font-weight:700;color:{_ACCENT};">오늘의 용어</div>'
                f'<div style="font-size:16px;font-weight:800;color:{_INK};margin-top:2px;">{_esc(tod["term"])}</div>'
                f'<div style="font-size:13px;color:{_INK};margin-top:4px;line-height:1.55;">{_esc(tod["long"])}</div>'
                f'{ana}</td></tr></table>'
            )
        if b.get("glossary"):
            chips = "".join(
                f'<span style="display:inline-block;background:#1e293b;border-radius:8px;'
                f'padding:5px 10px;margin:0 6px 6px 0;font-size:12px;color:{_INK};">'
                f'<b>{_esc(x["term"])}</b> {_esc(x["gloss"])}</span>'
                for x in b["glossary"])
            P.append(f'<div style="margin:0 0 12px;line-height:1.9;">{chips}</div>')

    # 심화 (small, gray)
    deep = []
    flow = {f["label"]: f for f in (b.get("daily_flow") or [])}
    vix, hy, ten = flow.get("VIX"), flow.get("HY spread"), flow.get("UST 10Y")
    if vix:
        deep.append(f'변동성 VIX {vix.get("value"):.1f} ({vix.get("chg5"):+.1f} 5일)')
    if hy:
        deep.append(f'신용 스프레드 {hy.get("value"):.2f}% ({hy.get("chg5_bp"):+d}bp, 벌어질수록 불안)')
    if ten:
        deep.append(f'美 10년 금리 {ten.get("value"):.2f}%')
    if b.get("extremes"):
        deep.append("선물 쏠림(반전 주의): " + " · ".join(f'{_esc(p["market"])}({_esc(p["extreme"])})' for p in b["extremes"]) + f' — CFTC ~{b.get("lag")}일 지연')
    if deep:
        inner = "".join(f'<div style="margin:3px 0;">· {d}</div>' for d in deep)
        P.append(f'<div style="font-size:12px;color:{_SUB};margin:6px 2px 4px;line-height:1.5;">'
                 f'<div style="font-weight:700;color:{_INK};margin-bottom:4px;">심화 (관심 있을 때만)</div>{inner}</div>')

    # footer
    P.append(f'<div style="border-top:1px solid {_LINE};margin-top:14px;padding-top:10px;'
             f'font-size:11px;color:{_SUB};line-height:1.6;">'
             f'데이터: yfinance(지수·섹터·종목) · CFTC · FRED · US Treasury<br>'
             f'목표주가·리테일심리 = 미표시(라이선스). 본 브리핑은 정보 제공이며 투자 권유가 아닙니다.</div>')

    P.append('</td></tr></table></div>')
    return "".join(P)


def render_page(b: dict) -> str:
    """Standalone web page wrapping the brief — written to docs/brief.html, served at /brief.html.
    Same body the email uses, so the web view and the inbox view never drift."""
    from engine.webnav import nav
    inner = render_html(b)
    return (
        '<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>시장심리 브리핑 — {_esc(b.get("as_of"))}</title>'
        f'<meta name="description" content="매일 아침 시장심리 브리핑 — {_esc(b.get("headline",""))}">'
        f'</head><body style="margin:0;background:{_BG};">{nav("home")}{inner}</body></html>'
    )
