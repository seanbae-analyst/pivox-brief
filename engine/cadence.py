"""8-K event cadence — Wave-3 refined signal (STRATEGY.md, the Δ-time "what's happening now" layer).

A static aggregator shows the *latest* 8-K. The signal an analyst assembles by hand is the
**cadence**: how often this issuer files material-event 8-Ks, whether that pace just picked up
or went quiet, and *what kind* of events dominate (earnings vs officer changes vs material
agreements vs "other"). A disclosure-cadence spike often leads the narrative — behavior leads
disclosure (STRATEGY.md §3).

Every output is an **observation + its count + the basis** — never a verdict (§10). Pure function
over already-fetched 8-K filings (``engine.edgar.Filing``-shaped: ``.filing_date`` + ``.items``),
so it unit-tests offline and adds no latency once the submissions list is in hand.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Optional

from engine.edgar import decode_items


def _as_date(s: str) -> Optional[date]:
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def eight_k_cadence(filings: list, as_of: Optional[str] = None,
                    window_days: int = 365) -> Optional[dict]:
    """Cadence of material-event 8-Ks from a list of 8-K filings (most-recent-first or any order).

    ``filings`` — objects with ``.filing_date`` (ISO) and ``.items`` (e.g. "2.02,9.01"); non-8-K
    forms are tolerated and ignored if ``.form`` is present. ``as_of`` anchors the trailing
    windows (defaults to today) so the comparison is testable. Returns None if no 8-K dates parse.
    """
    today = _as_date(as_of) if as_of else date.today()
    if today is None:
        today = date.today()

    dated = []
    for f in filings:
        if getattr(f, "form", "8-K") != "8-K":
            continue
        d = _as_date(getattr(f, "filing_date", None))
        if d is not None and d <= today:
            dated.append((d, getattr(f, "items", "") or ""))
    if not dated:
        return None

    dated.sort(key=lambda x: x[0])              # oldest → newest
    dates = [d for d, _ in dated]

    def _within(lo_days_ago: int, hi_days_ago: int = 0) -> list:
        return [d for d in dates if hi_days_ago <= (today - d).days < lo_days_ago]

    ttm = _within(window_days)
    prior_ttm = _within(2 * window_days, window_days)
    last_90 = _within(90)
    days_since_last = (today - dates[-1]).days

    # Average gap between consecutive filings within the trailing window (cadence rhythm).
    avg_gap = None
    if len(ttm) >= 2:
        gaps = [(ttm[i] - ttm[i - 1]).days for i in range(1, len(ttm))]
        avg_gap = round(sum(gaps) / len(gaps), 1)

    # Item mix over the trailing window — which kinds of events dominate.
    item_counter: Counter = Counter()
    for d, items in dated:
        if (today - d).days < window_days:
            for label in decode_items(items):
                item_counter[label] += 1
    item_mix = [{"label": lbl, "count": c} for lbl, c in item_counter.most_common(5)]

    # Pace classification vs the prior comparable window (descriptive, not a call).
    n, n_prior = len(ttm), len(prior_ttm)
    if n_prior == 0:
        pace = "baseline" if n else "quiet"
    elif n >= n_prior * 1.5 and n - n_prior >= 2:
        pace = "elevated"
    elif n <= n_prior * 0.5 and n_prior - n >= 2:
        pace = "quiet"
    else:
        pace = "steady"

    obs: list[str] = []
    pace_phrase = {
        "elevated": "elevated vs the prior 12 months",
        "quiet": "lighter than the prior 12 months",
        "steady": "in line with the prior 12 months",
        "baseline": "no prior-year 8-Ks on file to compare",
    }[pace]
    obs.append(
        f"Filed {n} material-event 8-K{'s' if n != 1 else ''} in the trailing 12 months "
        f"(vs {n_prior} in the prior 12) — disclosure cadence {pace_phrase}."
    )
    if len(last_90) >= 1:
        obs.append(f"{len(last_90)} in the last 90 days; {days_since_last} days since the most recent.")
    if item_mix:
        top = "; ".join(f"{m['label']} ({m['count']})" for m in item_mix[:3])
        obs.append(f"Most frequent event types (12mo): {top}.")

    return {
        "as_of": today.isoformat(),
        "window_days": window_days,
        "count_ttm": n,
        "count_prior_ttm": n_prior,
        "count_90d": len(last_90),
        "days_since_last": days_since_last,
        "avg_gap_days": avg_gap,
        "item_mix": item_mix,
        "pace": pace,
        "observations": obs,
        "note": "Disclosure-cadence description from official 8-K filing metadata — counts and "
                "event types only, not a verdict (§10).",
    }
