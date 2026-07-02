"""Shared top navigation — makes brief / research / settings feel like ONE site.

A single source for the header used across all pages (the brief renderer + the two page
generators import this), so the three views stop looking like separate sites. Links are
RELATIVE (./pack.html) — absolute "/" breaks on GitHub Pages project sites, where the app
lives under /pivox-brief/ and "/" is the (404) user root. Relative works on Vercel too.
"""
from __future__ import annotations

_LINKS = [
    ("home", "./pack.html", "📊 오늘의 시장"),
    ("settings", "./settings.html", "⚙️ 설정"),
]


def nav(active: str) -> str:
    items = []
    for key, href, label in _LINKS:
        on = key == active
        color = "#e2e8f0" if on else "#94a3b8"
        weight = "800" if on else "500"
        bb = "border-bottom:2px solid #d4a558;" if on else "border-bottom:2px solid transparent;"
        items.append(
            f'<a href="{href}" style="color:{color};text-decoration:none;font-weight:{weight};'
            f'font-size:14px;padding:14px 2px;{bb}">{label}</a>'
        )
    return (
        '<div style="background:#0a0e17;border-bottom:1px solid #334155;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;">'
        '<div style="max-width:960px;margin:0 auto;padding:0 16px;display:flex;gap:20px;align-items:center;">'
        '<a href="./pack.html" style="color:#d4a558;text-decoration:none;font-weight:800;font-size:16px;'
        'letter-spacing:.5px;padding:13px 0;margin-right:4px;">PIVOX</a>'
        + "".join(items)
        + '</div></div>'
    )
