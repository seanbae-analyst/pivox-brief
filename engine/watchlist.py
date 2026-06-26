"""User watchlist — which themes / custom tickers the brief is built around.

Persisted to data/watchlist.json (machine-local, gitignored). When absent, DEFAULT applies, so
the brief works out of the box. resolve() flattens the chosen themes + custom tickers into a
deduped (name, symbol) universe; sectors.py ranks today's movers within it. This JSON is also
the shape a future homepage picker would write — keep it simple and web-friendly.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.themes import THEMES

_PATH = Path(__file__).resolve().parent.parent / "data" / "watchlist.json"

_LEVELS = ("초보", "보통", "고수")  # how much hand-holding the brief gives

DEFAULT = {
    "themes": ["ai_semi", "battery_ev", "bigtech", "platform_kr"],
    "custom": [],          # list of bare symbols, e.g. ["TSLA", "005930.KS"]
    "explain_level": "초보",  # 주린이 default — max explanation
}


def load() -> dict:
    try:
        d = json.loads(_PATH.read_text(encoding="utf-8"))
        themes = [t for t in d.get("themes", []) if t in THEMES] or DEFAULT["themes"]
        custom = [s for s in d.get("custom", []) if isinstance(s, str) and s.strip()]
        level = d.get("explain_level") if d.get("explain_level") in _LEVELS else DEFAULT["explain_level"]
        return {"themes": themes, "custom": custom, "explain_level": level}
    except Exception:
        return dict(DEFAULT)


def save(wl: dict) -> None:
    themes = [t for t in wl.get("themes", []) if t in THEMES]
    custom = [s.strip() for s in wl.get("custom", []) if isinstance(s, str) and s.strip()]
    level = wl.get("explain_level") if wl.get("explain_level") in _LEVELS else DEFAULT["explain_level"]
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(
        json.dumps({"themes": themes, "custom": custom, "explain_level": level}, ensure_ascii=False, indent=2),
        encoding="utf-8")


def resolve(wl: dict | None = None) -> list[tuple[str, str]]:
    """Flatten chosen themes + custom tickers → deduped [(name, symbol)] universe."""
    wl = wl or load()
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for key in wl["themes"]:
        for name, sym in THEMES.get(key, {}).get("tickers", []):
            if sym not in seen:
                seen.add(sym)
                out.append((name, sym))
    for sym in wl["custom"]:
        if sym not in seen:
            seen.add(sym)
            out.append((sym, sym))  # custom: symbol doubles as label
    return out
