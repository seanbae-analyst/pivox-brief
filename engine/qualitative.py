"""Layer-2 qualitative extraction — official filing text → structured QualitativeBlock.

Two paths, one schema (engine.research_schema.QualitativeBlock):
- **$0 / in-session**: Claude Code reads the fetched section text and writes the block
  directly — how the demo packs are populated, no API spend.
- **Automated**: ``extract_via_api`` runs the same structured extraction through the
  Anthropic API (Haiku, cents-level) for the periodic refresh, when the operator opts in.

Sources are the company's OWN official filings only — 10-Q MD&A + 10-K Item 1A via
engine.filings. We derive structured facts + provenance links, never reproduce text (§1).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from engine import filings
from engine.research_schema import QualitativeBlock

# Extracted blocks are cached on disk (mirrors the link-only news cache) so the $0
# in-session extraction persists and the pack auto-loads it — same pattern as engine.news.
_QUAL_DIR = Path(__file__).resolve().parent.parent / "data" / "qualitative"


def load_qualitative(ticker: str) -> Optional[dict]:
    """Cached QualitativeBlock dump for a ticker, or None if absent/invalid. Validated
    against the schema on load, so a malformed cache file can never poison a pack."""
    p = _QUAL_DIR / f"{ticker.upper()}.json"
    if not p.exists():
        return None
    try:
        return QualitativeBlock(**json.loads(p.read_text(encoding="utf-8"))).model_dump(mode="json")
    except Exception:
        return None


def save_qualitative(ticker: str, block: Union[QualitativeBlock, dict]) -> Path:
    """Validate + persist an extracted block to data/qualitative/<TICKER>.json."""
    if not isinstance(block, QualitativeBlock):
        block = QualitativeBlock(**block)  # validate dicts before writing
    _QUAL_DIR.mkdir(parents=True, exist_ok=True)
    p = _QUAL_DIR / f"{ticker.upper()}.json"
    p.write_text(json.dumps(block.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


@dataclass
class FilingSources:
    mda: str
    risk: str
    mda_url: Optional[str]
    risk_url: Optional[str]


def fetch_sources(pack, mda_chars: int = 20000, risk_chars: int = 20000) -> FilingSources:
    """Fetch + slice the MD&A (latest 10-Q) and risk factors (latest 10-K) section text."""
    from engine.research_pack import earnings_read  # lazy: avoid import cycle

    read = earnings_read(pack.filings)
    q, k = read.get("latest_10q"), read.get("latest_10k")
    mda = filings.mda(filings.fetch_filing_text(q.url), max_chars=mda_chars) if q else ""
    risk = filings.risk_factors(filings.fetch_filing_text(k.url), max_chars=risk_chars) if k else ""
    return FilingSources(mda=mda, risk=risk,
                         mda_url=q.url if q else None, risk_url=k.url if k else None)


_SYSTEM = """You convert official SEC filing excerpts into ONE structured qualitative \
research record. You are given MD&A (from the 10-Q) and Risk Factors (Item 1A, from the \
10-K) for one company.

Rules:
- themes: map onto the provided fixed vocabulary ONLY; never invent values. Pick the 3-6 \
themes the filing most emphasizes (e.g. demand_strength, capex_investment, margin_pressure, \
competitive_pressure, pricing_power). For each: direction = is it a tailwind (positive), \
headwind (negative), or neutral FOR THE STOCK; evidence = a one-line paraphrase grounded in \
the text (NEVER verbatim); confidence in [0,1]; source_url = the filing URL it came from.
- guidance: did management raise / lower / maintain forward guidance, or none given \
(not_given)? Paraphrase the detail. Set source_url.
- tone: management's overall posture (confident / cautious / defensive / mixed). Score \
conservatively — tone is subjective.
- risk_factors: 3-6 paraphrased Item 1A risks most relevant to the stock (e.g. customer \
concentration, demand cyclicality, export controls). Paraphrase only, set source_url.
- Ground everything in the provided text. Do not use outside knowledge. Honest, calibrated \
confidence is the goal — low confidence is useful signal, not failure."""


def extract_via_api(sources: FilingSources, ticker: str, model: str = "claude-haiku-4-5") -> QualitativeBlock:
    """Automated extraction (Anthropic API, cents-level). Requires ANTHROPIC_API_KEY.
    The $0 default is the in-session path; this exists for the periodic refresh."""
    import anthropic

    client = anthropic.Anthropic()
    user = (
        f"Ticker: {ticker}\n\n"
        f"MD&A (10-Q — {sources.mda_url}):\n{sources.mda}\n\n"
        f"RISK FACTORS (10-K Item 1A — {sources.risk_url}):\n{sources.risk}"
    )
    resp = client.messages.parse(
        model=model,
        max_tokens=2048,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=QualitativeBlock,
    )
    return resp.parsed_output
