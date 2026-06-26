"""Watchlist resolve / theme taxonomy — pure, offline."""

from engine.themes import THEMES
from engine.watchlist import DEFAULT, resolve


def test_themes_have_tickers():
    for key, t in THEMES.items():
        assert t["label"] and t["tickers"], key
        for name, sym in t["tickers"]:
            assert name and sym


def test_resolve_unions_and_dedupes():
    # ai_semi + bigtech both exist; resolve should dedupe by symbol and keep both groups
    uni = resolve({"themes": ["ai_semi", "bigtech"], "custom": ["NVDA", "ZZZ"]})
    syms = [s for _, s in uni]
    assert len(syms) == len(set(syms))           # no dupes
    assert "NVDA" in syms and "ZZZ" in syms       # custom merged; NVDA not duplicated
    assert syms.count("NVDA") == 1


def test_resolve_default_nonempty():
    assert resolve(DEFAULT)


def test_resolve_drops_unknown_theme():
    uni = resolve({"themes": ["ai_semi", "not_a_theme"], "custom": []})
    assert uni and all(isinstance(s, str) for _, s in uni)
