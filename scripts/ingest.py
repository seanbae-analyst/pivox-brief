"""Ingest a Claude-Code-produced draft → validate + finalize (the $0 extraction path).

When extraction is run by Claude Code (an interactive session) instead of the
Anthropic API (engine/extract.py), the model output lands here as a JSON file
conforming to EarningsSignalDraft. This script validates it against the LOCKED
schema and runs the exact same confidence/review logic, so the *model step* is
interchangeable (API vs Claude Code vs local) while the engineering is identical.

    python scripts/ingest.py data/output/NVDA_Q1_FY2027.draft.json
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable when run as `python scripts/ingest.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.confidence import THRESHOLD, finalize  # noqa: E402
from engine.schema import EarningsSignalDraft       # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python scripts/ingest.py <draft.json>", file=sys.stderr)
        sys.exit(2)

    src = Path(sys.argv[1])
    draft = EarningsSignalDraft.model_validate_json(src.read_text(encoding="utf-8"))
    signal, warnings = finalize(draft)

    out = src.with_name(src.name.replace(".draft", "")) if ".draft" in src.name \
        else src.with_suffix(".final.json")
    out.write_text(signal.model_dump_json(indent=2), encoding="utf-8")

    print(signal.model_dump_json(indent=2))
    print()
    print(f"min confidence: {signal.confidence.min_dim():.2f}  (threshold {THRESHOLD})")
    print(f"needs_review: {signal.needs_review}")
    if warnings:
        print("sanity warnings:")
        for w in warnings:
            print(f"  - {w}")
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
