"""Standardized earnings-signal schema (PROJECT.md §3, Schema v0 — LOCKED).

This is the contract for the entire pipeline: the extractor must emit exactly this
shape, Pydantic validates it, and every downstream view reads it. Changing the field
set is a schema migration, not a casual edit.

Design note — the model produces `EarningsSignalDraft`; the pipeline derives
`needs_review` from the confidence threshold (PROJECT.md §6) to yield the final
`EarningsSignal`. Keeping the derived field out of the model's tool schema means the
LLM can't (accidentally or otherwise) self-approve.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from engine.taxonomy import KeyTheme


class GuidanceDirection(str, Enum):
    raised = "raised"
    lowered = "lowered"
    maintained = "maintained"
    not_given = "not_given"


class Tone(str, Enum):
    confident = "confident"
    cautious = "cautious"
    defensive = "defensive"
    mixed = "mixed"


class Metric(BaseModel):
    name: str                              # canonical key, e.g. "total_revenue"
    value_usd: Optional[float] = None      # normalized to a single unit (USD), §5①
    yoy_pct: Optional[float] = None
    qoq_pct: Optional[float] = None


class RatioUnit(str, Enum):
    percent = "percent"      # e.g. gross_margin = 74.9
    per_share = "per_share"  # e.g. eps = 1.87 (USD per share)


class Ratio(BaseModel):
    """Non-USD figures that don't fit Metric — margins, EPS (Schema v1; closes §5 gap)."""

    name: str          # e.g. "gross_margin", "operating_margin", "eps"
    value: float
    unit: RatioUnit


class Confidence(BaseModel):
    """Per-field confidence in [0, 1] (PROJECT.md §6)."""

    metrics: float = Field(ge=0.0, le=1.0)
    guidance: float = Field(ge=0.0, le=1.0)
    tone: float = Field(ge=0.0, le=1.0)
    themes: float = Field(ge=0.0, le=1.0)

    def min_dim(self) -> float:
        """Weakest dimension — drives review routing (engine.confidence)."""
        return min(self.metrics, self.guidance, self.tone, self.themes)


class EarningsSignalDraft(BaseModel):
    """Everything the extractor model produces (§3 minus derived fields)."""

    ticker: str
    period: str                            # e.g. "Q1 FY2027"
    call_date: str                         # ISO 8601
    headline_metrics: list[Metric]
    ratios: list[Ratio] = []               # margins, EPS — Schema v1 (optional, back-compat)
    guidance_direction: GuidanceDirection
    guidance_detail: Optional[str] = None
    key_themes: list[KeyTheme]             # controlled vocabulary only (§4)
    risk_factors: list[str]
    management_tone: Tone
    confidence: Confidence


class EarningsSignal(EarningsSignalDraft):
    """Final record = model draft + pipeline-derived fields."""

    needs_review: bool                     # derived from confidence threshold (§6)
