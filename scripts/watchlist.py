#!/usr/bin/env python3
"""View / edit the brief watchlist — which themes + tickers your 🔥 hot movers come from.

  python scripts/watchlist.py                      # show themes + current selection
  python scripts/watchlist.py set ai_semi,bio,defense   # choose themes (replaces)
  python scripts/watchlist.py add TSLA,005930.KS        # add custom tickers
  python scripts/watchlist.py clear-custom              # drop custom tickers
  python scripts/watchlist.py level 초보                # 설명 수준: 초보 / 보통 / 고수

Writes data/watchlist.json. The morning brief reads it on the next run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.themes import THEMES  # noqa: E402
from engine.watchlist import load, resolve, save  # noqa: E402


def _show() -> None:
    wl = load()
    print("테마 (선택하려면: set key1,key2,...)\n")
    for key, t in THEMES.items():
        mark = "☑" if key in wl["themes"] else "☐"
        names = ", ".join(n for n, _ in t["tickers"][:4]) + ("…" if len(t["tickers"]) > 4 else "")
        print(f"  {mark} {key:16} {t['label']:14} — {names}")
    print(f"\n내 종목(custom): {', '.join(wl['custom']) or '없음'}")
    print(f"설명 수준(explain_level): {wl.get('explain_level', '초보')}  (초보 / 보통 / 고수)")
    uni = resolve(wl)
    print(f"\n→ 핫 종목 후보 {len(uni)}개: " + ", ".join(n for n, _ in uni[:12]) + ("…" if len(uni) > 12 else ""))


def main() -> int:
    args = sys.argv[1:]
    if not args:
        _show()
        return 0
    cmd = args[0]
    wl = load()
    if cmd == "set" and len(args) > 1:
        keys = [k.strip() for k in args[1].split(",") if k.strip()]
        bad = [k for k in keys if k not in THEMES]
        if bad:
            print(f"모르는 테마: {', '.join(bad)}\n사용 가능: {', '.join(THEMES)}")
            return 1
        wl["themes"] = keys
        save(wl)
        print("저장됨.\n")
        _show()
    elif cmd == "add" and len(args) > 1:
        syms = [s.strip() for s in args[1].split(",") if s.strip()]
        wl["custom"] = list(dict.fromkeys(wl["custom"] + syms))
        save(wl)
        print("추가됨.\n")
        _show()
    elif cmd == "clear-custom":
        wl["custom"] = []
        save(wl)
        print("custom 비움.\n")
        _show()
    elif cmd == "level" and len(args) > 1:
        lv = args[1].strip()
        if lv not in ("초보", "보통", "고수"):
            print("수준은 초보 / 보통 / 고수 중 하나.")
            return 1
        wl["explain_level"] = lv
        save(wl)
        print(f"설명 수준 → {lv}\n")
        _show()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
