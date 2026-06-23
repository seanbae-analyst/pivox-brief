"""News layer — pure parsing, offline. The cache loader (load_news) is thin I/O."""

import json
import pathlib

from engine.news import NEWS_DIR, NewsItem, parse_news


def test_parse_news_keeps_valid_drops_incomplete():
    rows = [
        {"headline": "Chipmaker beats estimates", "url": "https://ex.com/a",
         "source": "Reuters", "date": "2026-06-20"},
        {"headline": "no url here"},          # dropped — missing url
        {"url": "https://ex.com/b"},          # dropped — missing headline
        {"headline": "Plain", "url": "https://ex.com/c"},
    ]
    items = parse_news(rows)
    assert len(items) == 2
    assert items[0] == NewsItem("Chipmaker beats estimates", "https://ex.com/a", "Reuters", "2026-06-20")
    assert items[1].source == "" and items[1].date == ""   # optional fields default empty


def test_committed_news_caches_are_valid():
    """Every committed data/news/*.json (US + KR) parses to real, linked items."""
    files = sorted(pathlib.Path(NEWS_DIR).glob("*.json"))
    assert files, "expected committed news caches"
    for f in files:
        rows = json.loads(f.read_text(encoding="utf-8"))
        items = parse_news(rows if isinstance(rows, list) else rows.get("items", []))
        assert items, f"{f.name}: no valid news items"
        assert all(it.url.startswith("http") for it in items), f"{f.name}: a url is malformed"
