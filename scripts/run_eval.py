"""Run the evaluation harness over verified goldset labels (PROJECT.md §7).

    python scripts/run_eval.py

Scores every prediction in data/output/ that has a matching, _verified goldset
file in data/goldset/. Prints per-record accuracy, calibration, and the threshold
sweep + headline sentence.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.evaluation import (  # noqa: E402
    calibration,
    score_record,
    target_sentence,
    threshold_sweep,
)
from engine.schema import EarningsSignal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    golds: dict[tuple[str, str], dict] = {}
    for g in sorted(glob.glob(str(ROOT / "data" / "goldset" / "*.gold.json"))):
        d = json.loads(Path(g).read_text(encoding="utf-8"))
        if not d.get("_verified"):
            print(f"skip (unverified): {Path(g).name}")
            continue
        golds[(d["ticker"], d["period"])] = d

    if not golds:
        print(
            "\nNo verified goldset files yet.\n"
            "  1) python scripts/make_goldset.py\n"
            "  2) edit data/goldset/*.gold.json — correct fields, set \"_verified\": true\n"
            "  3) re-run this script."
        )
        return

    pairs = []
    for p in sorted(glob.glob(str(ROOT / "data" / "output" / "*.json"))):
        if p.endswith(".draft.json"):
            continue
        sig = EarningsSignal.model_validate_json(Path(p).read_text(encoding="utf-8"))
        gold = golds.get((sig.ticker, sig.period))
        if gold:
            pairs.append((sig, gold))

    print(f"Scoring {len(pairs)} signal(s) with verified labels.\n")
    print(f"{'TICKER':7} {'guid':5} {'tone':5} {'themesF1':9} {'metrics':8} {'overall':7}")
    for sig, gold in pairs:
        s = score_record(sig, gold)
        print(
            f"{sig.ticker:7} {('OK' if s.guidance_correct else 'X'):5} "
            f"{('OK' if s.tone_correct else 'X'):5} {s.themes_f1:9.2f} "
            f"{s.metrics_accuracy:8.2f} {s.overall:7.2f}"
        )

    print("\nCALIBRATION (confidence band -> observed accuracy):")
    for dim in ("metrics", "guidance", "tone", "themes"):
        bs = calibration(pairs, dim)
        cells = "  ".join(f"[{b.lo:.2f}-{b.hi:.2f}] {b.accuracy:.0%} (n={b.n})" for b in bs)
        print(f"  {dim:9} {cells or '(no data)'}")

    print("\nTHRESHOLD SWEEP:")
    print(f"  {'tau':5} {'auto%':7} {'autoAcc':8} {'review%':7}")
    for r in threshold_sweep(pairs):
        print(f"  {r.threshold:<5} {r.auto_rate:7.0%} {r.auto_accuracy:8.2f} {r.review_burden:7.0%}")

    print("\n>>> " + target_sentence(pairs))


if __name__ == "__main__":
    main()
