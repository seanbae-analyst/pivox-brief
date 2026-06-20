"""Confidence derivation + human-in-the-loop routing (PROJECT.md §6).

Phase 1 wires two of §6's three signals: (1) the model's self-reported confidence
and (2) deterministic sanity rules. The strongest signal — (3) a cross-model /
repeated-run consistency check — is Phase 2, stubbed below.

`THRESHOLD` is the central PM lever (§6): at/above it a record auto-approves,
below it routes to human review. 0.85 is a placeholder until the eval harness
(§7) tells us where to actually put it.
"""

from __future__ import annotations

from engine.schema import EarningsSignal, EarningsSignalDraft

THRESHOLD = 0.85  # auto-approve at/above, human-review below — to be set by eval (§7)


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


def derive_needs_review(draft: EarningsSignalDraft, warnings: list[str]) -> bool:
    """Route to human review on low confidence OR any failed sanity rule."""
    return draft.confidence.min_dim() < THRESHOLD or bool(warnings)


def finalize(draft: EarningsSignalDraft) -> tuple[EarningsSignal, list[str]]:
    """Draft → final EarningsSignal with the derived needs_review flag."""
    warnings = sanity_warnings(draft)
    signal = EarningsSignal.model_validate(
        {**draft.model_dump(), "needs_review": derive_needs_review(draft, warnings)}
    )
    return signal, warnings


def consistency_check(*args, **kwargs):  # noqa: ANN002, ANN003 — Phase 2
    """§6 signal ③ (strongest): Haiku×2 or Haiku-vs-Sonnet agreement. TODO Phase 2."""
    raise NotImplementedError("Phase 2: cross-model / repeat-run agreement scoring")
