"""Fetch earnings-day market reactions for every signal (L1/L2 input).

    python scripts/fetch_reactions.py

Writes data/reactions.json keyed by ticker. Free daily prices via yfinance.
Descriptive event-study data only — not a trading signal (§10).
"""

from __future__ import annotations

import glob
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.prices import event_return  # noqa: E402
from engine.schema import EarningsSignal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    out = {}
    finals = [p for p in sorted(glob.glob(str(ROOT / "data" / "output" / "*.json")))
              if not p.endswith(".draft.json")]
    for p in finals:
        sig = EarningsSignal.model_validate_json(Path(p).read_text(encoding="utf-8"))
        r = event_return(sig.ticker, sig.call_date)
        if r:
            out[sig.ticker] = asdict(r)
            print(f"{sig.ticker:6} {sig.call_date}  {r.close_before} -> {r.close_after}  {r.event_return_pct:+.2f}%")
        else:
            print(f"{sig.ticker:6} {sig.call_date}  (no data)")
        time.sleep(0.6)

    dest = ROOT / "data" / "reactions.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {dest}  ({len(out)} reactions)")


if __name__ == "__main__":
    main()
