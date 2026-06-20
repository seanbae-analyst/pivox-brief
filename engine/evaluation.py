"""Evaluation harness (PROJECT.md §7) — the portfolio's heart.

Scores standardized signals against a hand-labeled goldset and answers the two
questions the product lives or dies on:
  1. Accuracy — per field, how often is the extraction right?
  2. Calibration — when the model self-reports confidence 0.9, is it ~90% right?
…then sweeps the auto-approve threshold (§6) to produce the §7 target sentence:
  "At threshold 0.85: N% auto-processed, guidance accuracy M%, review burden R%."

All functions are pure (no API, no I/O) so they unit-test offline.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.schema import EarningsSignal


# ── per-record scoring ────────────────────────────────────────────────────────
@dataclass
class FieldScores:
    guidance_correct: bool
    tone_correct: bool
    themes_precision: float
    themes_recall: float
    themes_f1: float
    metrics_accuracy: float   # fraction of gold metrics matched within tolerance
    metrics_matched: int
    metrics_total: int

    @property
    def overall(self) -> float:
        """Unweighted mean of the four gradeable axes, in [0, 1]."""
        return (
            float(self.guidance_correct)
            + float(self.tone_correct)
            + self.themes_f1
            + self.metrics_accuracy
        ) / 4.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


def score_metrics(
    pred: EarningsSignal, gold_metrics: dict[str, float], *, rel_tol: float = 0.02
) -> tuple[int, int, float]:
    """Fraction of gold metrics whose predicted value (matched by name) is within tol.

    Name-matching is exact for v0 — a prediction that calls revenue "total_revenue"
    while the gold calls it "revenue" counts as a miss. Metric-name normalization is
    a known v1 candidate (surfaces as a measurable gap here rather than silently).
    """
    pred_by_name = {m.name: m.value_usd for m in pred.headline_metrics}
    matched = 0
    for name, gold_val in gold_metrics.items():
        pv = pred_by_name.get(name)
        if pv is None or gold_val is None:
            continue
        denom = max(abs(pv), abs(gold_val), 1.0)
        if abs(pv - gold_val) / denom <= rel_tol:
            matched += 1
    total = len(gold_metrics)
    return matched, total, (matched / total if total else 1.0)


def score_record(pred: EarningsSignal, gold: dict) -> FieldScores:
    """Score one prediction against its gold label across the gradeable fields (§7)."""
    guidance_correct = pred.guidance_direction.value == gold["guidance_direction"]
    tone_correct = pred.management_tone.value == gold["management_tone"]

    pred_themes = {t.value for t in pred.key_themes}
    gold_themes = set(gold["key_themes"])
    tp = len(pred_themes & gold_themes)
    precision = tp / len(pred_themes) if pred_themes else (1.0 if not gold_themes else 0.0)
    recall = tp / len(gold_themes) if gold_themes else 1.0
    f1 = _f1(precision, recall)

    m_matched, m_total, m_acc = score_metrics(pred, gold.get("metrics", {}))
    return FieldScores(
        guidance_correct, tone_correct, precision, recall, f1, m_acc, m_matched, m_total
    )


# ── calibration ───────────────────────────────────────────────────────────────
@dataclass
class CalibrationBucket:
    lo: float
    hi: float
    n: int
    accuracy: float   # observed accuracy of the dimension within this confidence band


def _dim_correct(scores: FieldScores, dimension: str) -> bool:
    if dimension == "guidance":
        return scores.guidance_correct
    if dimension == "tone":
        return scores.tone_correct
    if dimension == "themes":
        return scores.themes_f1 >= 0.5
    if dimension == "metrics":
        return scores.metrics_accuracy >= 0.5
    raise ValueError(f"unknown dimension: {dimension}")


def calibration(
    pairs: list[tuple[EarningsSignal, dict]],
    dimension: str,
    bins: tuple[float, ...] = (0.0, 0.6, 0.7, 0.8, 0.9, 1.01),
) -> list[CalibrationBucket]:
    """Bucket records by a dimension's self-reported confidence, measure actual accuracy.

    If 'confidence 0.9' really means ~90% correct, the high bands should track high.
    With a tiny goldset this is illustrative, not statistically meaningful — that's
    expected; the harness is the deliverable, the N grows over time.
    """
    points = [
        (getattr(pred.confidence, dimension), _dim_correct(score_record(pred, gold), dimension))
        for pred, gold in pairs
    ]
    buckets = []
    for lo, hi in zip(bins, bins[1:]):
        band = [ok for c, ok in points if lo <= c < hi]
        if band:
            buckets.append(CalibrationBucket(lo, hi, len(band), sum(band) / len(band)))
    return buckets


# ── threshold sweep (§6 ↔ §7) ─────────────────────────────────────────────────
@dataclass
class SweepRow:
    threshold: float
    auto_rate: float       # fraction auto-approved (min confidence dim >= threshold)
    auto_accuracy: float   # mean overall score of the auto-approved records
    review_burden: float   # fraction routed to human review
    n_auto: int
    n_total: int


def threshold_sweep(
    pairs: list[tuple[EarningsSignal, dict]],
    thresholds: tuple[float, ...] = (0.70, 0.75, 0.80, 0.85, 0.90),
) -> list[SweepRow]:
    """For each candidate threshold: auto-approve rate, accuracy of the auto-approved
    subset, and review burden. This is the table that turns §6's threshold knob into
    a defensible PM decision."""
    scored = [
        (pred.confidence.min_dim(), score_record(pred, gold).overall) for pred, gold in pairs
    ]
    n = len(scored)
    rows = []
    for tau in thresholds:
        auto = [ov for mn, ov in scored if mn >= tau]
        n_auto = len(auto)
        rows.append(
            SweepRow(
                threshold=tau,
                auto_rate=n_auto / n if n else 0.0,
                auto_accuracy=sum(auto) / n_auto if n_auto else 0.0,
                review_burden=(n - n_auto) / n if n else 0.0,
                n_auto=n_auto,
                n_total=n,
            )
        )
    return rows


def target_sentence(pairs: list[tuple[EarningsSignal, dict]], threshold: float = 0.85) -> str:
    """The §7 headline sentence at a chosen threshold."""
    row = threshold_sweep(pairs, (threshold,))[0]
    guidance_acc = (
        sum(score_record(p, g).guidance_correct for p, g in pairs) / len(pairs) if pairs else 0.0
    )
    return (
        f"At threshold {threshold}: {row.auto_rate:.0%} auto-processed, "
        f"guidance accuracy {guidance_acc:.0%}, review burden {row.review_burden:.0%} "
        f"(n={row.n_total})."
    )
