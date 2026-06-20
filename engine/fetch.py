"""Transcript loading (PROJECT.md §8): local file first, FMP as fallback.

Phase 1 runs on a single transcript, so the primary path is a local file under
data/transcripts/. FMP fetching is a convenience for later phases / live runs.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import requests

TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "transcripts"


def _slug(period: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", period.strip()).strip("_")


def local_path(ticker: str, period: str) -> Path:
    """e.g. ("NVDA", "Q1 FY2027") -> data/transcripts/NVDA_Q1_FY2027.txt"""
    return TRANSCRIPTS_DIR / f"{ticker.upper()}_{_slug(period)}.txt"


def load_local(ticker: str, period: str) -> str | None:
    p = local_path(ticker, period)
    return p.read_text(encoding="utf-8") if p.exists() else None


def fetch_fmp(ticker: str, year: int, quarter: int) -> str:
    """Fetch a transcript from Financial Modeling Prep.

    NOTE: confirm the exact endpoint against your FMP plan (stable vs v3) before
    relying on this — it uses the long-standing v3 path. Phase 1 normally runs
    from a local file, so this is convenience, not the critical path.
    """
    key = os.environ.get("FMP_API_KEY")
    if not key:
        raise RuntimeError(
            "FMP_API_KEY not set; drop the transcript as a .txt under " + str(TRANSCRIPTS_DIR)
        )
    url = (
        "https://financialmodelingprep.com/api/v3/earning_call_transcript/"
        f"{ticker.upper()}?year={year}&quarter={quarter}&apikey={key}"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise RuntimeError(f"FMP returned no transcript for {ticker} {year} Q{quarter}")
    record = data[0] if isinstance(data, list) else data
    return record["content"]
