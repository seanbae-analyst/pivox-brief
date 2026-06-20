"""Phase 1 extraction engine — transcript → EarningsSignalDraft (PROJECT.md §8).

Uses the Anthropic structured-outputs API (`messages.parse`) with the locked
Pydantic schema: the model can only return schema-valid output, and the SDK
validates it client-side. This is the structured-output primitive the spec calls
for (§8) — cleaner than hand-rolled tool use for a pure-extraction task.

Model routing follows §8's cost lever: bulk extraction on Haiku 4.5, escalation
to Sonnet 4.6 only when the model's own confidence is low. The stable system
prompt is cache-flagged so re-runs across a watchlist pay ~0.1x for the prefix.
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic

from engine.schema import EarningsSignalDraft

HAIKU = "claude-haiku-4-5"     # bulk extraction ($1/$5 per Mtok) — §8
SONNET = "claude-sonnet-4-6"   # escalation for ambiguous / tone calls — §8

# Escalate to the stronger model when the weakest confidence dimension is below
# this. Shares the review threshold for v0; eval may split them later (§6/§7).
ESCALATE_BELOW = 0.85

_SYSTEM = """You are a financial-data standardization engine. You convert ONE \
earnings-call transcript into ONE structured EarningsSignal record.

Rules:
- Map free text onto the provided fixed vocabularies only. Never invent enum values.
- key_themes: choose only from the controlled vocabulary; use __other__ when nothing \
fits. Prefer the 2-5 themes the transcript actually emphasizes, not every theme touched on.
- headline_metrics: the figures management leads with (revenue, key segments, margins, \
EPS). Normalize every value to absolute USD in value_usd (e.g. "$81.6 billion" -> \
81600000000). Prefer the most precise figure stated. Leave a field null if not stated.
- guidance_direction: did management raise / lower / maintain forward guidance vs the \
prior outlook, or was none given (not_given)?
- management_tone: the overall posture across the call.
- confidence: for EACH field group (metrics, guidance, tone, themes) report your own \
calibrated confidence in [0,1]. Be honest — low confidence is useful signal, not failure. \
Tone is subjective; score it conservatively.
- Use the authoritative ticker / period / call_date from the user message verbatim.
- Ground everything in this transcript. Do not use outside knowledge of the company."""


@dataclass
class ExtractInfo:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    escalated: bool


def _extract_once(
    client: anthropic.Anthropic,
    transcript: str,
    ticker: str,
    period: str,
    call_date: str,
    model: str,
) -> tuple[EarningsSignalDraft, ExtractInfo]:
    user = (
        "Authoritative metadata (use verbatim):\n"
        f"- ticker: {ticker}\n- period: {period}\n- call_date: {call_date}\n\n"
        "Earnings-call transcript:\n\n"
        f"{transcript}"
    )
    resp = client.messages.parse(
        model=model,
        max_tokens=4096,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=EarningsSignalDraft,
    )
    u = resp.usage
    info = ExtractInfo(
        model=model,
        input_tokens=u.input_tokens,
        output_tokens=u.output_tokens,
        cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        escalated=False,
    )
    return resp.parsed_output, info


def extract_signal(
    transcript: str,
    ticker: str,
    period: str,
    call_date: str,
    *,
    model: str = HAIKU,
    escalate: bool = True,
) -> tuple[EarningsSignalDraft, ExtractInfo]:
    """Extract one draft; escalate Haiku→Sonnet when self-confidence is low (§8)."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    draft, info = _extract_once(client, transcript, ticker, period, call_date, model)
    if escalate and model == HAIKU and draft.confidence.min_dim() < ESCALATE_BELOW:
        draft, info = _extract_once(client, transcript, ticker, period, call_date, SONNET)
        info.escalated = True
    return draft, info
