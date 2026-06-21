# Pivox Brief — Case Study
### Earnings Call Standardization Engine

**An AI pipeline that turns long, free-text earnings-call transcripts into comparable,
schema-validated signal records — and measures how much you can trust each one.**

> Spec / source of truth: [PROJECT.md](PROJECT.md). This document is the proof.
> Built end-to-end for **$0** (see §7).

---

## 1. Problem
Earnings-call transcripts are tens of pages of free text per company. Guidance direction,
management tone, and recurring risks/themes are all in there — but with no structure, you
**can't compare** across a watchlist without reading every one. Hand-labeling doesn't scale;
rule-based parsing breaks because every company phrases things differently.

The real question isn't just *"can AI standardize this?"* — it's **"can the system know when it
*can't* be trusted?"** A standardizer you can't audit is worse than no standardizer.

## 2. What I built
```
transcript ──► AI extraction (structured output) ──► Pydantic validation
                                                          │
                          confidence (3 signals) ─────────┤
                                                          ▼
                              needs_review? ── no ──► auto-approve
                                    │
                                   yes ─────────────► human-review queue
                                                          ▲
                              eval harness ──────────────┘  (accuracy · calibration · threshold)
```
- **Schema as contract** — `EarningsSignal` (Pydantic): metrics (USD-normalized), guidance
  direction, management tone, controlled-vocab themes, per-field confidence.
- **Controlled vocabulary** — 16 themes + `__other__`, typed as an enum so an out-of-vocab
  theme is *unrepresentable* (comparability by construction, not by prompt request).
- **Confidence, 3 signals (§6)** — model self-report · deterministic sanity rules ·
  cross-run consistency (extract twice, measure agreement).
- **Routing** — `needs_review` derived when the weakest confidence dim < threshold.
- **Eval harness (§7)** — per-field accuracy, calibration, and a threshold sweep.

## 3. Key decisions (each explainable in one line)
| Decision | Choice | Why |
|---|---|---|
| Output contract | `EarningsSignalDraft` → `EarningsSignal` split | model fills the draft; pipeline derives `needs_review`, so the LLM can't self-approve |
| Themes | controlled-vocab **enum** (16 + `__other__`) | out-of-vocab themes can't be represented → watchlist-wide comparison by construction |
| Structured output | `messages.parse()` (structured outputs), not hand-rolled tool use | schema-valid by construction + client-side validation, for a pure-extraction task |
| Model routing | Haiku 4.5 bulk → Sonnet 4.6 escalation *(designed; see §8)* | cheapest model that clears confidence; escalate only ambiguous cases |
| Number precision | press-release precise (`$81,615M`), call figure verifies | the call rounds ("$82B"); a 2% match tolerance absorbs the gap |
| Confidence threshold | `min(dim) < τ → review`; **τ set by eval** | the threshold is a data decision, not a guess |
| $0 runtime | **Claude Code as the extraction engine** | zero marginal cost using existing tooling; `extract.py` kept as the API scale path |

## 4. Results (n = 9 — NVDA, MSFT, GOOGL, AMD, AMZN, JPM, WMT, XOM, UNH)
A 9-company watchlist spanning AI/tech plus a bank, retailer, energy major, and health insurer:
guidance **100%**, tone **100%**, metrics **100%**, themes F1 **~0.95** (NVDA 0.80, JPM 0.86,
XOM 0.89; the rest 1.00 — the misses are genuine theme-mapping judgment calls, not extraction errors).

**Threshold sweep** (auto-approve at `min confidence ≥ τ`):

| τ | auto-processed | accuracy of auto-approved | review burden |
|---|:--:|:--:|:--:|
| 0.70 | 78% | 0.99 | 22% |
| 0.75 | 56% | 0.99 | 44% |
| 0.80 | 22% | 1.00 | 78% |
| 0.85 | 11% | 1.00 | 89% |
| 0.90 | 0%  | —    | 100% |

> **At threshold 0.85: 11% auto-processed, guidance accuracy 100%, review burden 89% (n=9).**

## 5. What the eval taught me (the point of §7)
- **The default threshold (0.85) is far too conservative for this set.** At 0.85 only 11%
  auto-approves; dropping to 0.70 lifts that to **78%** at **0.99** accuracy on the auto-approved
  subset. The eval is literally telling me where to put the §6 knob (~0.70–0.75 here).
- **The model is systematically *under-confident* on thin/messy input.** MSFT (garbled capture,
  metrics confidence 0.68) and XOM (sparse disclosure — no revenue/EPS stated, confidence 0.55)
  both self-doubted, yet every metric they *did* report was correct. "I don't trust this source"
  and "this number is wrong" are different doubts and should be scored separately.
- **Schema v0 has a real gap.** Gross margin (74.9%) and EPS don't fit a USD-only `Metric`, so
  they're silently dropped. → **Schema v1: a percent / per-share metric type.**
- **Metric-name matching is brittle.** Scoring matches metrics by exact name; `total_revenue`
  vs `revenue` would count as a miss. → **v1: metric-name normalization.**

## 6. Trustworthiness *is* the product
The routing column is the deliverable, not a side effect:
- **AMD** (clean source, clear narrative) → `needs_review = false`, auto-approved.
- **NVDA / GOOGL / MSFT** → routed to human review, each for a different weak dimension
  (NVDA themes 0.78, GOOGL themes 0.80, MSFT metrics 0.68).

The system answered §1's real question: it knew which records to doubt.

## 7. Cost: $0
| Component | Production target (§8) | This build | Cost |
|---|---|---|---|
| Storage | Supabase | repo-local JSON | $0 |
| Transcripts | FMP (paid tier) | public sources → `.txt` | $0 |
| Runtime / scheduler | GitHub Actions cron | on-demand | $0 |
| Dashboard | hosted | static / deferred | $0 |
| **AI extraction** | Haiku/Sonnet via API | **Claude Code as engine** | **$0** |

The only irreducible production cost is the Claude API. At this scale (~4 transcripts × extract +
consistency) that's roughly **$1–3** on Haiku ($1/$5 per Mtok), trimmed further by prompt
caching and the Batch API — and typically covered by Anthropic free credits. It was **not
incurred here**: `engine/extract.py` is the ready-to-run API path; the portfolio sample was run
through Claude Code at zero marginal cost.

## 8. Limitations (honest)
- **n = 9** — better, but still *illustrative, not statistical*. The harness is the deliverable; N grows.
- **Single-annotator goldset** — I labeled both the extractions and the truth. Themes accuracy is
  therefore *intra-annotator consistency*; NVDA's 0.80 reflects my own two reads diverging
  (`market_share_gain` vs `capex_investment`). An independent labeler is future work.
- **8 of 9 transcripts are condensed captures** (WebFetch summarized long pages), so objective
  extraction was easier than full messy text. Only NVDA used a near-verbatim transcript.
- **TSLA deferred** — no free full transcript was readily fetchable.

## 9. Roadmap
1. Scale further (now 9 → 20–40) → calibration becomes statistically meaningful.
2. Independent themes labeling (remove the intra-annotator caveat).
3. Schema v1 — percent/per-share metric type (margins, EPS) + metric-name normalization.
4. Full verbatim transcripts for the whole set.
5. Run a sample through the API → real $ figure + Haiku-vs-Opus accuracy delta.
6. Static two-view dashboard (system performance / earnings intelligence) on GitHub Pages.

---
### Reproduce
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest -q                       # 16 offline tests
python scripts/run_eval.py      # scores committed signals vs the verified goldset
```
*(Raw transcripts and intermediate drafts are gitignored — publisher copyright; the final
`EarningsSignal` outputs and the goldset are committed, so `run_eval.py` reproduces §4.)*
