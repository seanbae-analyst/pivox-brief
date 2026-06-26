"""Management-tone trajectory across quarters — Wave-3 refined signal (STRATEGY.md, Δ-time).

A snapshot tells you this quarter's MD&A reads cautious. The *signal* is the **trajectory**: is
management's language getting more negative / more uncertain quarter over quarter, or easing? We
measure it the way finance research does — **Loughran-McDonald lexical density** (the standard,
auditable approach for 10-K/10-Q text): count negative / uncertainty / positive words per 1,000
words of the MD&A, across the last N filings, and describe the direction.

This is deliberately NOT an opaque "sentiment score." Every number traces to counted words in the
official filing — you can audit it. It is descriptive, never a verdict (§10): we report the
density and its direction; the reader judges what it means.

The scorer (``score_tone`` / ``build_trajectory``) is pure and unit-tested offline. The I/O
orchestrator (``tone_trajectory``) fetches the last few MD&As and is gated by callers because it
fetches several large filing documents (latency).
"""

from __future__ import annotations

import re
from typing import Optional

# Compact Loughran-McDonald-style finance lexicons. Not the full LM dictionary (thousands of
# terms) — a curated, high-signal subset matched as word-prefixes so inflections count. The
# methodology (LM 2011, "When Is a Liability Not a Liability?") is the citation; the density is
# transparent and reproducible from the filing text.
_NEGATIVE = (
    "adverse", "decline", "decrease", "loss", "losses", "weak", "weaken", "litigation", "lawsuit",
    "impair", "shortfall", "downturn", "deteriorat", "default", "breach", "penalt", "restructur",
    "writeoff", "write-off", "writedown", "headwind", "slowdown", "unfavorab", "difficult",
    "challeng", "disrupt", "shortage", "delay", "failure", "fail",
)
_UNCERTAINTY = (
    "uncertain", "may", "could", "might", "risk", "possib", "approximat", "depend", "fluctuat",
    "volatil", "unpredictab", "exposure", "contingen", "assum", "estimate", "believe", "anticipat",
    "potential", "subject to",
)
_POSITIVE = (
    "improve", "improvement", "growth", "grew", "increase", "strong", "strength", "gain", "record",
    "favorab", "robust", "expand", "outperform", "efficien", "profitab", "momentum", "accelerat",
    "exceed", "success", "opportunit",
)

_WORD = re.compile(r"[a-z][a-z\-]+")


def _density(words: list[str], lexicon: tuple[str, ...]) -> float:
    """Hits per 1,000 words — a lexicon hit = a word starting with any lexicon prefix."""
    if not words:
        return 0.0
    hits = sum(1 for w in words if any(w.startswith(p) for p in lexicon))
    return round(hits / len(words) * 1000.0, 1)


def score_tone(text: str) -> dict:
    """Loughran-McDonald-style lexical densities for one MD&A text (per 1,000 words).

    ``net_tone`` = positive − negative density (a transparent net, not a black-box score). Returns
    zeros for empty text so a missing MD&A degrades gracefully instead of raising."""
    words = _WORD.findall((text or "").lower())
    neg = _density(words, _NEGATIVE)
    unc = _density(words, _UNCERTAINTY)
    pos = _density(words, _POSITIVE)
    return {
        "words": len(words),
        "negative_density": neg,
        "uncertainty_density": unc,
        "positive_density": pos,
        "net_tone": round(pos - neg, 1),
    }


def _direction(vals: list[float], eps: float = 1.0) -> str:
    """Plain-language trajectory of a short series (oldest → newest)."""
    xs = [v for v in vals if v is not None]
    if len(xs) < 2:
        return "n/a"
    delta = xs[-1] - xs[0]
    if abs(delta) <= eps:
        return "flat"
    return "rising" if delta > 0 else "falling"


def build_trajectory(docs: list[tuple[str, str]]) -> Optional[dict]:
    """Tone trajectory from ``[(period_label, mda_text), ...]`` ordered oldest → newest.

    Pure: callers fetch the MD&As, this scores and describes the path. Returns None if fewer than
    two scorable periods (a trajectory needs ≥2 points)."""
    scored = [{"period": label, **score_tone(text)} for label, text in docs if (text or "").strip()]
    if len(scored) < 2:
        return None

    net = [s["net_tone"] for s in scored]
    neg = [s["negative_density"] for s in scored]
    unc = [s["uncertainty_density"] for s in scored]
    net_dir = _direction(net)
    neg_dir = _direction(neg)
    unc_dir = _direction(unc)

    seq = " → ".join(f"{s['period']}:{s['net_tone']:+g}" for s in scored)
    obs = [
        f"Net tone (positive − negative word density /1k) across {len(scored)} quarters: "
        f"{seq} — {net_dir}.",
        f"Negative-word density {neg_dir} ({neg[0]:g} → {neg[-1]:g} /1k); "
        f"uncertainty-word density {unc_dir} ({unc[0]:g} → {unc[-1]:g} /1k).",
    ]
    return {
        "method": "Loughran-McDonald-style lexical density (per 1,000 words of MD&A)",
        "periods": scored,
        "net_tone_direction": net_dir,
        "negative_direction": neg_dir,
        "uncertainty_direction": unc_dir,
        "observations": obs,
        "note": "Transparent word-density measure from official MD&A text — auditable, descriptive, "
                "not a sentiment verdict or advice (§10).",
    }


def tone_trajectory(filings: list, max_docs: int = 4) -> Optional[dict]:
    """Fetch the last ``max_docs`` MD&A-bearing filings (10-Q/10-K, newest-first input) and build the
    trajectory. Gated by callers — fetches several large filing documents. Never raises: a fetch
    failure drops that quarter; returns None if <2 quarters score."""
    from engine import edgar
    from engine.filings import fetch_filing_text, mda

    picked = [f for f in filings if getattr(f, "form", "") in ("10-Q", "10-K")][:max_docs]
    docs: list[tuple[str, str]] = []
    for f in reversed(picked):                      # oldest → newest for the trajectory
        try:
            text = mda(fetch_filing_text(f.url))
        except Exception:
            continue
        if text:
            label = getattr(f, "report_date", None) or getattr(f, "filing_date", "")
            docs.append((label, text))
    try:
        return build_trajectory(docs)
    except Exception:
        return None
