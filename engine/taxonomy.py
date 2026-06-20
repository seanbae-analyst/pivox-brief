"""Controlled vocabulary for `key_themes` (PROJECT.md §4, v0).

The model MAPS free text onto these fixed themes — it never invents new ones.
`__other__` is the escape hatch; its share across a corpus is the taxonomy-health
metric (§4): a persistently high rate means the taxonomy needs new entries.

Typing `key_themes` to this enum (see engine.schema) makes an out-of-vocabulary
theme *unrepresentable* — both Pydantic and the tool JSON-schema reject it — so the
"매핑만, 자유 생성 금지" rule is enforced by construction, not by a prompt request.
"""

from __future__ import annotations

from enum import Enum


class KeyTheme(str, Enum):
    demand_strength = "demand_strength"
    demand_weakness = "demand_weakness"
    pricing_power = "pricing_power"
    margin_expansion = "margin_expansion"
    margin_pressure = "margin_pressure"
    capex_investment = "capex_investment"
    supply_constraint = "supply_constraint"
    new_product_ramp = "new_product_ramp"
    market_share_gain = "market_share_gain"
    competitive_pressure = "competitive_pressure"
    cost_efficiency = "cost_efficiency"
    m_and_a = "M&A"
    regulatory_legal = "regulatory_legal"
    macro_headwind = "macro_headwind"
    capital_return = "capital_return"
    segment_expansion = "segment_expansion"
    other = "__other__"  # escape hatch


OTHER = KeyTheme.other

# Real taxonomy hits (everything except the escape hatch).
CORE_THEMES: list[KeyTheme] = [t for t in KeyTheme if t is not KeyTheme.other]


def other_rate(themes: list[KeyTheme]) -> float:
    """Share of `__other__` in a theme list — the taxonomy-health signal (§4)."""
    if not themes:
        return 0.0
    return sum(1 for t in themes if t is KeyTheme.other) / len(themes)
