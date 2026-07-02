#!/usr/bin/env python3
"""Inject the daily brief (research-styled cards) into the top of pack.html's home view, so the
homepage is ONE page: market brief + ticker search + featured packs, all in the same design.

Run after build_site.py (which regenerates pack.html) and before commit/deploy. Idempotent —
strips any prior injection first. Degrades to a no-op if the brief build fails (page untouched).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

PACK = ROOT / "docs" / "pack.html"
MARK = "<!--BRIEF-HOME-->"
SLOT = "<!--BRIEF-SLOT-->"   # template anchor — brief renders below the search command bar


def main() -> int:
    if not PACK.is_file():
        print("pack.html missing — run build_site first", file=sys.stderr)
        return 1
    html = PACK.read_text(encoding="utf-8")
    # remove any previous injection (idempotent)
    html = re.sub(re.escape(MARK) + ".*?" + re.escape(MARK), "", html, flags=re.S)

    try:
        from engine.brief import build_brief
        from engine.brief_home import render_home_cards
        cards = render_home_cards(build_brief())
    except Exception as e:
        print(f"brief build failed — leaving pack.html as-is: {e}", file=sys.stderr)
        PACK.write_text(html, encoding="utf-8")
        return 0

    block = f"{MARK}{cards}{MARK}"
    if SLOT in html:                       # dashboard layout: brief sits under the command bar
        html = html.replace(SLOT, SLOT + block, 1)
    else:                                  # legacy template fallback
        html = html.replace('<section id="home">', '<section id="home">' + block, 1)
    PACK.write_text(html, encoding="utf-8")
    print(f"injected brief into {PACK} ({len(cards)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
