"""Cross-company earnings intelligence (PROJECT.md §2, dashboard View 2).

Turns the standardized signals into watchlist-level analysis: which themes
dominate the quarter, how guidance/tone are distributed, who leads on growth,
and how many records still need review.

Descriptive / comparative ONLY — this is a data-intelligence layer, not
investment advice (§10). No "buy/sell", no recommendations.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from engine.schema import EarningsSignal


def theme_frequency(signals: list[EarningsSignal]) -> list[tuple[str, int]]:
    c = Counter(t.value for s in signals for t in s.key_themes)
    return c.most_common()


def guidance_distribution(signals: list[EarningsSignal]) -> dict[str, int]:
    return dict(Counter(s.guidance_direction.value for s in signals))


def tone_distribution(signals: list[EarningsSignal]) -> dict[str, int]:
    return dict(Counter(s.management_tone.value for s in signals))


def review_rate(signals: list[EarningsSignal]) -> tuple[int, int, float]:
    n = len(signals)
    r = sum(1 for s in signals if s.needs_review)
    return r, n, (r / n if n else 0.0)


def metric_ranking(
    signals: list[EarningsSignal], metric_name: str, by: str = "yoy_pct"
) -> list[tuple[str, float]]:
    """Rank tickers by a field (yoy_pct/qoq_pct/value_usd) of a named metric, desc."""
    rows = []
    for s in signals:
        for m in s.headline_metrics:
            if m.name == metric_name:
                val = getattr(m, by)
                if val is not None:
                    rows.append((s.ticker, val))
                break
    return sorted(rows, key=lambda x: -x[1])


def headlines(signals: list[EarningsSignal]) -> list[str]:
    """Plain-language, comparative observations (no advice)."""
    out: list[str] = []
    n = len(signals)
    if not n:
        return out
    gd = Counter(s.guidance_direction.value for s in signals)
    top_g = gd.most_common(1)[0]
    out.append(f"{top_g[1]} of {n} companies {top_g[0]} guidance.")
    tf = theme_frequency(signals)
    if tf:
        out.append(f"Most common theme: '{tf[0][0]}' ({tf[0][1]} of {n} companies).")
    rr = metric_ranking(signals, "total_revenue", "yoy_pct")
    if rr:
        out.append(f"Fastest revenue growth: {rr[0][0]} (+{rr[0][1]:.0f}% YoY).")
    r, nn, rate = review_rate(signals)
    out.append(f"{r} of {nn} records flagged for human review ({rate:.0%}).")
    return out


@dataclass
class Intelligence:
    n: int
    theme_frequency: list[tuple[str, int]]
    guidance: dict[str, int]
    tone: dict[str, int]
    revenue_growth: list[tuple[str, float]]
    review: tuple[int, int, float]
    headlines: list[str]


def analyze(signals: list[EarningsSignal]) -> Intelligence:
    return Intelligence(
        n=len(signals),
        theme_frequency=theme_frequency(signals),
        guidance=guidance_distribution(signals),
        tone=tone_distribution(signals),
        revenue_growth=metric_ranking(signals, "total_revenue", "yoy_pct"),
        review=review_rate(signals),
        headlines=headlines(signals),
    )
