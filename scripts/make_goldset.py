"""Generate goldset label templates from predictions (PROJECT.md §7).

Each template is pre-filled with the MODEL's own prediction, so labeling becomes
*correcting* rather than typing from scratch. Review each field against the
transcript, fix what's wrong, then set "_verified": true. run_eval.py scores only
verified golds.

(Caveat: pre-filling can anchor the labeler — verify against the transcript, don't
rubber-stamp. Blank-template labeling is a more rigorous v1 option.)

    python scripts/make_goldset.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.schema import EarningsSignal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "goldset"


def main() -> None:
    GOLD.mkdir(parents=True, exist_ok=True)
    preds = [
        p for p in sorted(glob.glob(str(ROOT / "data" / "output" / "*.json")))
        if not p.endswith(".draft.json")
    ]
    made = 0
    for p in preds:
        sig = EarningsSignal.model_validate_json(Path(p).read_text(encoding="utf-8"))
        out = GOLD / f"{sig.ticker}_{sig.period.replace(' ', '_')}.gold.json"
        if out.exists():
            print(f"skip (exists): {out.name}")
            continue
        template = {
            "_verified": False,
            "_instructions": "Correct each field against the transcript, then set _verified to true.",
            "ticker": sig.ticker,
            "period": sig.period,
            "guidance_direction": sig.guidance_direction.value,
            "management_tone": sig.management_tone.value,
            "key_themes": [t.value for t in sig.key_themes],
            "metrics": {m.name: m.value_usd for m in sig.headline_metrics},
        }
        out.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        made += 1
        print(f"wrote {out.name}")
    print(f"\n{made} template(s) written to {GOLD}")
    if made:
        print("Next: edit each .gold.json, correct fields, set \"_verified\": true, then run scripts/run_eval.py")


if __name__ == "__main__":
    main()
