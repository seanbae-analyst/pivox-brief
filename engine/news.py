"""News & catalysts — headline + link only (DATA_SOURCES.md §4).

We never reproduce article bodies; a news item is just headline + source + url +
date. Discovery (web search) is a separable layer: items are injected through a
local cache at ``data/news/<TICKER>.json``, which a search step writes and the
tool reads. That keeps the research pack itself $0 and deterministic — and keeps
the legal posture simple (we publish only links to others' headlines, never text).

Cache format — a JSON list (or ``{"items": [...]}``) of objects:
    [{"headline": "...", "url": "https://...", "source": "Reuters", "date": "2026-06-20"}]
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

NEWS_DIR = Path(__file__).resolve().parent.parent / "data" / "news"


@dataclass
class NewsItem:
    headline: str
    url: str
    source: str = ""
    date: str = ""


def parse_news(rows: list[dict]) -> list[NewsItem]:
    """Validate raw cache rows -> NewsItem list. Drops rows missing headline/url."""
    out: list[NewsItem] = []
    for r in rows:
        headline, url = r.get("headline"), r.get("url")
        if headline and url:
            out.append(NewsItem(headline=str(headline), url=str(url),
                                 source=str(r.get("source", "")), date=str(r.get("date", ""))))
    return out


def load_news(ticker: str) -> list[NewsItem]:
    """Cached headlines for a ticker, or [] if none. Never raises."""
    path = NEWS_DIR / f"{ticker.upper()}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return parse_news(data if isinstance(data, list) else data.get("items", []))
