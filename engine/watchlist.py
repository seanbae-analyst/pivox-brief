"""User watchlist — which themes / custom tickers the brief is built around.

Persisted to data/watchlist.json (machine-local, gitignored). When absent, DEFAULT applies, so
the brief works out of the box. resolve() flattens the chosen themes + custom tickers into a
deduped (name, symbol) universe; sectors.py ranks today's movers within it. This JSON is also
the shape a future homepage picker would write — keep it simple and web-friendly.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

from engine.themes import THEMES

# Custom tickers become display labels verbatim on the public homepage, and the
# picker table is world-writable via the anon key — so an unrestricted string
# here is a stored-XSS vector. Constrain to the same ticker charset the search
# API enforces (letters/digits/dot/hyphen), which cannot break out of an HTML
# attribute or inject markup.
_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")

_PATH = Path(__file__).resolve().parent.parent / "data" / "watchlist.json"
_TABLE = "brief_settings"
_ROW = "default"  # single-user app → one settings row

_LEVELS = ("초보", "보통", "고수")  # how much hand-holding the brief gives

DEFAULT = {
    "themes": ["ai_semi", "battery_ev", "bigtech", "platform_kr"],
    "custom": [],          # list of bare symbols, e.g. ["TSLA", "005930.KS"]
    "explain_level": "초보",  # 주린이 default — max explanation
}


def _validate(d: dict) -> dict:
    themes = [t for t in d.get("themes", []) if t in THEMES] or DEFAULT["themes"]
    custom = [s.strip() for s in d.get("custom", []) if isinstance(s, str) and _TICKER_RE.match(s.strip())]
    level = d.get("explain_level") if d.get("explain_level") in _LEVELS else DEFAULT["explain_level"]
    return {"themes": themes, "custom": custom, "explain_level": level}


def _supabase_env() -> tuple[str, str] | None:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY")
    return (url.rstrip("/"), key) if (url and key) else None


def _remote_load() -> dict | None:
    """Read the selection the public picker page saved to Supabase. None if unconfigured/down."""
    env = _supabase_env()
    if not env:
        return None
    url, key = env
    try:
        r = requests.get(
            f"{url}/rest/v1/{_TABLE}",
            params={"id": f"eq.{_ROW}", "select": "themes,custom,explain_level"},
            headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=8,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None
    except Exception:
        return None


def load() -> dict:
    # priority: Supabase (homepage picker) → local file (CLI) → DEFAULT
    remote = _remote_load()
    if remote:
        return _validate(remote)
    try:
        return _validate(json.loads(_PATH.read_text(encoding="utf-8")))
    except Exception:
        return dict(DEFAULT)


def save(wl: dict) -> None:
    themes = [t for t in wl.get("themes", []) if t in THEMES]
    custom = [s.strip() for s in wl.get("custom", []) if isinstance(s, str) and _TICKER_RE.match(s.strip())]
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
