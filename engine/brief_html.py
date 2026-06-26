"""HTML email renderer for the morning brief — the 'make it visual' layer.

Email clients (Gmail especially) are hostile: no <style> reliability, no flexbox, no JS. So
this is table-based with INLINE styles only, single column, max-width 600, system fonts.
Colors follow the Korean convention (상승=빨강, 하락=파랑) since the reader is Korean and the
brief leads with the KR market; arrows (▲▼) carry direction independent of color.
"""
from __future__ import annotations

_UP, _DN, _FLAT = "#d12b2b", "#1f6feb", "#6b7280"
_INK, _SUB, _LINE, _BG, _CARD = "#16181d", "#5b6470", "#e6e8ec", "#f4f5f7", "#ffffff"


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _col(x) -> str:
    if x is None:
        return _FLAT
    return _UP if x > 0 else (_DN if x < 0 else _FLAT)


def _arr(x) -> str:
    return "▲" if (x or 0) > 0 else ("▼" if (x or 0) < 0 else "—")


def _bar(x, cap=12.0, maxw=70) -> str:
    """Tiny proportional bar (table cells with bgcolor — the one bar style email renders)."""
    if x is None:
        return ""
    w = max(2, int(min(abs(x) / cap, 1.0) * maxw))
    rest = maxw - w
    cells = f'<td width="{w}" height="7" style="background:{_col(x)};font-size:0;line-height:0;border-radius:3px;">&nbsp;</td>'
    if rest > 0:
        cells += f'<td width="{rest}" height="7" style="font-size:0;line-height:0;">&nbsp;</td>'
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;"><tr>{cells}</tr></table>')


def _rows(items: list[dict]) -> str:
    out = []
    for i in items:
        x = i.get("chg5_pct")
        out.append(
            f'<tr>'
            f'<td style="padding:6px 0;font-size:14px;color:{_INK};white-space:nowrap;">{_esc(i["label"])}</td>'
            f'<td style="padding:6px 10px;width:74px;">{_bar(x)}</td>'
            f'<td style="padding:6px 0;text-align:right;font-size:14px;font-weight:700;'
            f'color:{_col(x)};white-space:nowrap;font-variant-numeric:tabular-nums;">'
            f'{_arr(x)} {x:+.1f}%</td>'
            f'</tr>'
        )
    return "".join(out)


def _card(flag: str, title: str, sub: str, body: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:separate;background:{_CARD};border:1px solid {_LINE};'
        f'border-radius:14px;margin:0 0 14px;">'
        f'<tr><td style="padding:16px 18px;">'
        f'<div style="font-size:15px;font-weight:800;color:{_INK};letter-spacing:-.2px;">{flag} {_esc(title)}'
        f'<span style="font-weight:500;color:{_SUB};font-size:12px;">  {_esc(sub)}</span></div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:8px;">{body}</table>'
        f'</td></tr></table>'
    )


def _callout(text: str, color: str, bg: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:separate;margin:2px 0 10px;"><tr>'
        f'<td style="padding:10px 14px;background:{bg};border-left:3px solid {color};'
        f'border-radius:8px;font-size:13px;color:{_INK};line-height:1.5;">{text}</td>'
        f'</tr></table>'
    )


def render_html(b: dict) -> str:
    sectors = b.get("sectors") or {}
    us = sectors.get("us") or []
    kr = sectors.get("kr") or []
    us_idx = [i for i in us if i["group"] == "지수"]
    us_sec = [i for i in us if i["group"] == "섹터"]
    kr_idx = [i for i in kr if i["group"] == "지수"]
    kr_fx = next((i for i in kr if i["group"] == "환율"), None)
    kr_stk = [i for i in kr if i["group"] in ("반도체", "2차전지", "자동차")]

    risk = b.get("headline", "")
    band = (_UP, "#fdeaea") if "회피" in risk else (("#157f3b", "#e9f7ee") if "선호" in risk else (_SUB, "#eef0f3"))

    P = []
    P.append(f'<div style="background:{_BG};padding:18px 12px;">')
    P.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
             f'style="max-width:600px;margin:0 auto;border-collapse:collapse;font-family:'
             f'-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;">')
    P.append('<tr><td>')

    # header
    P.append(f'<div style="font-size:20px;font-weight:800;color:{_INK};letter-spacing:-.4px;">'
             f'📊 시장심리 브리핑</div>'
             f'<div style="font-size:12px;color:{_SUB};margin:2px 0 12px;">{_esc(b.get("as_of"))} · 아침</div>')

    # headline pill + plain
    P.append(f'<div style="display:inline-block;padding:8px 14px;border-radius:999px;'
             f'background:{band[1]};color:{band[0]};font-weight:800;font-size:15px;">{_esc(risk)}</div>')
    if b.get("plain"):
        P.append(f'<div style="font-size:13px;color:{_SUB};margin:8px 2px 14px;line-height:1.55;">{_esc(b["plain"])}</div>')
    else:
        P.append('<div style="height:12px;"></div>')

    # alerts
    if b.get("alerts"):
        items = "".join(f'<div style="margin:3px 0;">• {_esc(a)}</div>' for a in b["alerts"])
        P.append(_callout(f'<b>🚨 큰 움직임</b><div style="margin-top:4px;">{items}</div>', _UP, "#fdeaea"))

    # US card
    body = ""
    if us_idx:
        body += _rows(us_idx)
    if us_sec:
        if body:
            body += f'<tr><td colspan="3" style="border-top:1px solid {_LINE};padding-top:2px;"></td></tr>'
        body += _rows(us_sec)
    if body:
        P.append(_card("🇺🇸", "미국장", "어제 마감 · 5일 변화", body))
        if b.get("us_rotation"):
            P.append(_callout(f'<b>한눈에</b>  {_esc(b["us_rotation"])}', band[0], "#f7f8fa"))

    # KR card
    body = ""
    if kr_idx:
        body += _rows(kr_idx)
    if kr_fx:
        won = "원화 약세" if (kr_fx["chg5_pct"] or 0) > 0 else "원화 강세"
        body += (f'<tr><td style="padding:6px 0;font-size:14px;color:{_INK};">원/달러</td>'
                 f'<td style="padding:6px 10px;width:74px;">{_bar(kr_fx["chg5_pct"])}</td>'
                 f'<td style="padding:6px 0;text-align:right;font-size:14px;font-weight:700;color:{_col(kr_fx["chg5_pct"])};white-space:nowrap;">'
                 f'{kr_fx["last"]:,.0f}원 ({won})</td></tr>')
    if kr_stk:
        body += f'<tr><td colspan="3" style="border-top:1px solid {_LINE};padding-top:2px;"></td></tr>'
        body += _rows(kr_stk)
    if body:
        P.append(_card("🇰🇷", "한국장", "오늘 마감 · 5일 변화", body))
        if b.get("kr_read"):
            P.append(_callout(f'<b>한눈에</b>  {_esc(b["kr_read"])}', band[0], "#f7f8fa"))

    # watch
    if b.get("watch"):
        P.append(_callout(f'<b>⚠️ 주목</b>  {_esc(b["watch"])}', "#b7791f", "#fdf6e3"))

    # 심화 (small, gray)
    deep = []
    flow = {f["label"]: f for f in (b.get("daily_flow") or [])}
    vix = flow.get("VIX"); hy = flow.get("HY spread"); ten = flow.get("UST 10Y")
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
