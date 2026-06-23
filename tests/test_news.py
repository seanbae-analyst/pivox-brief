"""News layer — pure parsing, offline. The cache loader (load_news) is thin I/O."""

from engine.news import NewsItem, parse_news


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
