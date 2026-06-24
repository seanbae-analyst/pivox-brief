"""Typed schema for the research pack's qualitative layer (Layer 2).

The quant layer is plain computed numbers (engine.factors); the qualitative layer is
*extracted from filing text* and so benefits from validation — it's typed with Pydantic
and reuses the LOCKED controlled vocabularies from engine.schema / engine.taxonomy
(KeyTheme, Tone, GuidanceDirection). An out-of-vocabulary theme is unrepresentable (the
enum rejects it), so "map onto the fixed vocabulary, never invent" is enforced by
construction — same guarantee the earnings engine relies on.

Every signal carries a confidence in [0,1] and a ``source_url`` back to the official
filing it came from (provenance, DATA_SOURCES.md §1). ``evidence``/``summary`` are short
derived paraphrases — never verbatim reproduction of the filing text.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from engine.schema import GuidanceDirection, Tone
from engine.taxonomy import KeyTheme


class ThemeDirection(str, Enum):
    """Whether the theme reads as a tailwind, headwind, or neutral for the stock."""

    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class ResearchTheme(BaseModel):
    theme: KeyTheme                       # controlled vocabulary only (engine.taxonomy)
    direction: ThemeDirection
    evidence: str                         # one-line paraphrase grounded in the filing
    confidence: float = Field(ge=0.0, le=1.0)
    source_url: str


class GuidanceSignal(BaseModel):
    direction: GuidanceDirection
    detail: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_url: Optional[str] = None


class ToneSignal(BaseModel):
    label: Tone
    confidence: float = Field(ge=0.0, le=1.0)
    source_url: Optional[str] = None


class RiskFactor(BaseModel):
    summary: str                          # paraphrased risk (derived, not reproduced)
    source_url: str


class QualitativeBlock(BaseModel):
    """Layer-2 record: filings-derived signal for the narrative read. Comparable across
    issuers because every theme maps onto the fixed taxonomy."""

    guidance: Optional[GuidanceSignal] = None
    tone: Optional[ToneSignal] = None
    themes: list[ResearchTheme] = []
    risk_factors: list[RiskFactor] = []
    sources: list[str] = []               # the filing URLs read to build this block
