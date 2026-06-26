"""Shared top navigation — makes brief / research / settings feel like ONE site.

A single source for the header used across all pages (the brief renderer + the two page
generators import this), so the three views stop looking like separate sites. Links use
explicit .html paths so they work on both Vercel and GitHub Pages.
"""
from __future__ import annotations

_LINKS = [
    ("brief", "/brief.html", "📊 브리핑"),
    ("research", "/pack.html", "🔍 리서치"),
    ("settings", "/settings.html", "⚙️ 설정"),
]


def nav(active: str) -> str:
    items = []
    for key, href, label in _LINKS:
        on = key == active
        color = "#0f172a" if on else "#64748b"
        weight = "800" if on else "500"
        bb = "border-bottom:2px solid #0d9488;" if on else "border-bottom:2px solid transparent;"
        items.append(
            f'<a href="{href}" style="color:{color};text-decoration:none;font-weight:{weight};'
            f'font-size:14px;padding:14px 2px;{bb}">{label}</a>'
        )
    return (
        '<div style="background:#fff;border-bottom:1px solid #e6e8ec;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;">'
        '<div style="max-width:960px;margin:0 auto;padding:0 16px;display:flex;gap:20px;align-items:center;">'
        '<a href="/brief.html" style="color:#15171c;text-decoration:none;font-weight:800;font-size:16px;'
        'letter-spacing:-.3px;padding:13px 0;margin-right:4px;">Pivox</a>'
        + "".join(items)
        + '</div></div>'
    )
