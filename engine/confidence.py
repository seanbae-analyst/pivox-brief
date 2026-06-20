"""Confidence derivation + human-in-the-loop routing (PROJECT.md §6).

§6 lists three confidence signals; this module implements all three:
  ① the model's self-reported confidence (already on the schema),
  ② deterministic sanity rules (`sanity_warnings`),
  ③ cross-run consistency — the strongest signal — via `agreement` /
     `run_with_consistency` (extract twice, measure how much the runs agree).

`THRESHOLD` and `CONSISTENCY_FLOOR` are the central PM levers (§6): they decide
auto-approve vs human review. The values here are placeholders until the eval
harness (§7) tells us where they actually belong.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.schema import EarningsSignal, EarningsSignalDraft

THRESHOLD = 0.85          # self-reported confidence floor for auto-approve (§7)
CONSISTENCY_FLOOR = 0.75  # cross-run agreement floor for auto-approve (§7)


# ── signal ② : deterministic sanity rules ────────────────────────────────────
def sanity_warnings(draft: EarningsSignalDraft) -> list[str]:
    """Deterministic checks (§6 signal ②): values in sane ranges, fields present."""
    w: list[str] = []
    if not draft.key_themes:
        w.append("no key_themes extracted")
    if not draft.headline_metrics:
        w.append("no headline_metrics extracted")
    for m in draft.headline_metrics:
        if m.value_usd is not None and m.value_usd < 0:
            w.append(f"metric {m.name!r} has negative value_usd")
        for label, pct in (("yoy", m.yoy_pct), ("qoq", m.qoq_pct)):
            if pct is not None and not -100.0 <= pct <= 1000.0:
                w.append(f"metric {m.name!r} {label}_pct out of sane range: {pct}")
    return w


# ── signal ③ : cross-run consistency (the strongest signal, §6) ───────────────
@dataclass
class Agreement:
    """How much two independent extractions of the same transcript agree."""

    guidance_match: bool
    tone_match: bool
    themes_jaccard: float   # set overlap of key_themes
    metrics_overlap: float  # shared metric names with values within tolerance
    score: float            # unweighted mean of the four, in [0, 1]

    @property
    def consistent(self) -> bool:
        return self.score >= CONSISTENCY_FLOOR


def _theme_values(d: EarningsSignalDraft) -> set[str]:
    return {t.value for t in d.key_themes}


def _values_close(x: float | None, y: float | None, rel_tol: float) -> bool:
    if x is None or y is None:
        return x is y  # both None counts as agreement; one None does not
    denom = max(abs(x), abs(y), 1.0)
    return abs(x - y) / denom <= rel_tol


def agreement(a: EarningsSignalDraft, b: EarningsSignalDraft, *, rel_tol: float = 0.02) -> Agreement:
    """Field-by-field agreement between two drafts of the same transcript."""
    guidance_match = a.guidance_direction == b.guidance_direction
    tone_match = a.management_tone == b.management_tone

    ta, tb = _theme_values(a), _theme_values(b)
    themes_jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 1.0

    ma = {m.name: m for m in a.headline_metrics}
    mb = {m.name: m for m in b.headline_metrics}
    union = set(ma) | set(mb)
    agreed = sum(
        1 for n in (set(ma) & set(mb)) if _values_close(ma[n].value_usd, mb[n].value_usd, rel_tol)
    )
    metrics_overlap = agreed / len(union) if union else 1.0

    score = (guidance_match + tone_match + themes_jaccard + metrics_overlap) / 4.0
    return Agreement(guidance_match, tone_match, themes_jaccard, metrics_overlap, score)


def run_with_consistency(
    transcript: str, ticker: str, period: str, call_date: str
):
    """Extract twice on Haiku and score cross-run agreement (§6 ③).

    Returns (first_draft, Agreement, (info_a, info_b)). The double call is the
    cost of the strongest confidence signal — gate it on cheaper signals in
    production. Imported lazily so the pure functions above stay anthropic-free.
    """
    from engine.extract import HAIKU, extract_signal

    a, info_a = extract_signal(transcript, ticker, period, call_date, model=HAIKU, escalate=False)
    b, info_b = extract_signal(transcript, ticker, period, call_date, model=HAIKU, escalate=False)
    return a, agreement(a, b), (info_a, info_b)


# ── routing ───────────────────────────────────────────────────────────────────
def derive_needs_review(
    draft: EarningsSignalDraft, warnings: list[str], ag: Agreement | None = None
) -> bool:
    """Route to human review on low self-confidence, a failed rule, or disagreement."""
    if draft.confidence.min_dim() < THRESHOLD:
        return True
    if warnings:
        return True
    if ag is not None and not ag.consistent:
        return True
    return False


def finalize(
    draft: EarningsSignalDraft, ag: Agreement | None = None
) -> tuple[EarningsSignal, list[str]]:
    """Draft → final EarningsSignal with the derived needs_review flag.

    Pass `ag` (from `run_with_consistency`) to fold the §6 ③ signal into routing.
    """
    warnings = sanity_warnings(draft)
    signal = EarningsSignal.model_validate(
        {**draft.model_dump(), "needs_review": derive_needs_review(draft, warnings, ag)}
    )
    return signal, warnings
