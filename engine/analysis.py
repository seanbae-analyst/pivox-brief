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


def ratio_ranking(signals: list[EarningsSignal], ratio_name: str) -> list[tuple[str, float]]:
    """Rank tickers by a named ratio (e.g. gross_margin), desc — where disclosed."""
    rows = []
    for s in signals:
        for r in s.ratios:
            if r.name == ratio_name:
                rows.append((s.ticker, r.value))
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
    gm = ratio_ranking(signals, "gross_margin")
    if gm:
        out.append(f"Highest gross margin: {gm[0][0]} ({gm[0][1]:.1f}%).")
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
    gross_margin: list[tuple[str, float]]
    review: tuple[int, int, float]
    headlines: list[str]


def analyze(signals: list[EarningsSignal]) -> Intelligence:
    return Intelligence(
        n=len(signals),
        theme_frequency=theme_frequency(signals),
        guidance=guidance_distribution(signals),
        tone=tone_distribution(signals),
        revenue_growth=metric_ranking(signals, "total_revenue", "yoy_pct"),
        gross_margin=ratio_ranking(signals, "gross_margin"),
        review=review_rate(signals),
        headlines=headlines(signals),
    )


# ── market reaction (L1/L2) — descriptive only, NOT investment advice (§10) ────
_GUIDANCE_SCORE = {"raised": 1, "maintained": 0, "lowered": -1, "not_given": 0}
_TONE_SCORE = {"confident": 1, "mixed": 0, "cautious": -1, "defensive": -1}


def signal_lean(sig: EarningsSignal) -> int:
    """Coarse signal direction in {-1, 0, 1} from guidance + tone (heuristic)."""
    s = _GUIDANCE_SCORE.get(sig.guidance_direction.value, 0) + _TONE_SCORE.get(
        sig.management_tone.value, 0
    )
    return (s > 0) - (s < 0)


def _lean_label(v: int) -> str:
    return {1: "positive", 0: "neutral", -1: "negative"}[v]


def reaction_by_lean(signals: list[EarningsSignal], reactions: dict) -> dict[str, float]:
    """Average earnings-day return grouped by signal lean — does the signal align (L1)?"""
    from collections import defaultdict

    buckets: dict[str, list[float]] = defaultdict(list)
    for s in signals:
        r = reactions.get(s.ticker)
        if r is None:
            continue
        buckets[_lean_label(signal_lean(s))].append(r["event_return_pct"])
    return {k: round(sum(v) / len(v), 2) for k, v in buckets.items()}


def divergences(signals: list[EarningsSignal], reactions: dict, *, min_move: float = 2.0) -> list[dict]:
    """Cases where the signal and the market reaction point opposite ways (L2)."""
    out = []
    for s in signals:
        r = reactions.get(s.ticker)
        if r is None:
            continue
        lean, ret = signal_lean(s), r["event_return_pct"]
        if lean > 0 and ret <= -min_move:
            out.append({"ticker": s.ticker, "lean": "positive", "reaction": ret,
                        "note": "signal positive, market fell"})
        elif lean < 0 and ret >= min_move:
            out.append({"ticker": s.ticker, "lean": "negative", "reaction": ret,
                        "note": "signal negative, market rose"})
    return sorted(out, key=lambda d: abs(d["reaction"]), reverse=True)
