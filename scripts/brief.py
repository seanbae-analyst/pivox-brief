#!/usr/bin/env python3
"""Generate the morning market-psychology brief.

  python scripts/brief.py            # build, print, save md, persist snapshot
  python scripts/brief.py --send     # also email it (key-gated; inert without SENDGRID_API_KEY)
  python scripts/brief.py --check    # alerts only — exit 10 if a big event fired (for cron)
  python scripts/brief.py --quiet    # build + save but don't print body (cron-friendly)

The --check mode is the 'something big happened' trigger: it builds, prints any alerts,
and signals via exit code (10 = alert fired) so a wrapper can fire an out-of-band push
without sending the full daily digest.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from engine.brief import build_brief, persist  # noqa: E402

_OUT = Path(__file__).resolve().parent.parent / "data" / "output"


def main() -> int:
    args = set(sys.argv[1:])
    brief = build_brief()

    if "--check" in args:
        if brief["alerts"]:
            print(f"🚨 {brief['as_of']} — 큰 움직임 {len(brief['alerts'])}건")
            for a in brief["alerts"]:
                print(f"   • {a}")
            from engine.notify import send_brief
            print(f"[delivery] {send_brief(brief)}")  # push the alert (key-gated)
            persist(brief)  # record so the same event doesn't re-alert tomorrow
            return 10
        print(f"{brief['as_of']} — 알림 없음 (조용)")
        return 0

    if "--quiet" not in args:
        print(brief["text"])

    _OUT.mkdir(parents=True, exist_ok=True)
    md = _OUT / f"brief_{brief['date']}.md"
    md.write_text(brief["text"] + "\n", encoding="utf-8")
    persist(brief)

    if "--send" in args:
        from engine.notify import send_brief
        print(f"[delivery] {send_brief(brief)}")

    if "--quiet" in args:
        print(f"wrote {md}  | quiet={brief['quiet']} | alerts={len(brief['alerts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
