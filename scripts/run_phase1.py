"""Phase 1 entrypoint: NVDA Q1 FY2027 transcript → standardized EarningsSignal.

    python scripts/run_phase1.py

Requires ANTHROPIC_API_KEY (in .env). Provide the transcript either as a local
file at data/transcripts/NVDA_Q1_FY2027.txt, or set FMP_API_KEY to fetch it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Make the project root importable when run as `python scripts/run_phase1.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.confidence import THRESHOLD, finalize          # noqa: E402
from engine.extract import extract_signal                  # noqa: E402
from engine.fetch import fetch_fmp, load_local, local_path  # noqa: E402

# Test case — PROJECT.md §11.
TICKER = "NVDA"
PERIOD = "Q1 FY2027"
CALL_DATE = "2026-05-20"
FMP_YEAR, FMP_QUARTER = 2027, 1

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "output"


def _load_transcript() -> str:
    text = load_local(TICKER, PERIOD)
    if text:
        print(f"Loaded transcript from {local_path(TICKER, PERIOD)}")
        return text
    if os.environ.get("FMP_API_KEY"):
        print("No local transcript; fetching from FMP…")
        return fetch_fmp(TICKER, FMP_YEAR, FMP_QUARTER)
    print(
        "No transcript found.\n"
        f"  Drop it at: {local_path(TICKER, PERIOD)}\n"
        "  or set FMP_API_KEY in .env to fetch it.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY not set — copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        sys.exit(1)

    transcript = _load_transcript()
    print(f"Transcript length: {len(transcript):,} chars\n")

    draft, info = extract_signal(transcript, TICKER, PERIOD, CALL_DATE)
    signal, warnings = finalize(draft)

    print(signal.model_dump_json(indent=2))
    print()
    print(f"model: {info.model}" + (" (escalated Haiku→Sonnet)" if info.escalated else ""))
    print(
        f"tokens: in={info.input_tokens} out={info.output_tokens} "
        f"cache_read={info.cache_read_tokens}"
    )
    print(f"min confidence: {signal.confidence.min_dim():.2f}  (threshold {THRESHOLD})")
    print(f"needs_review: {signal.needs_review}")
    if warnings:
        print("sanity warnings:")
        for msg in warnings:
            print(f"  - {msg}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{TICKER}_{PERIOD.replace(' ', '_')}.json"
    out.write_text(signal.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
