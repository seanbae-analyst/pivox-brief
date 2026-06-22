# Pivox Brief — Earnings Call Standardization Engine

Turns long, free-text earnings-call transcripts into **comparable, standardized
signal records** — and proves how trustworthy that standardization is.

> Single source of truth: **[PROJECT.md](PROJECT.md)**. Every build decision defers to it.
> 📊 Results & write-up: **[CASE_STUDY.md](CASE_STUDY.md)**.

## What it does
Given an earnings transcript, the engine emits a typed `EarningsSignal` — guidance
direction, management tone, controlled-vocabulary themes, USD-normalized metrics —
plus a per-field **confidence** score. Low-confidence records route to a human-review
queue; high-confidence records auto-approve. The threshold is set by the eval harness,
not by guesswork (PROJECT.md §6–§7).

This is a **data-standardization / intelligence tool, not an investment-signal tool**
(PROJECT.md §10).

## Status
**Phases 0–6 + a stock-price layer** (schema · extraction · confidence routing · eval · dashboard ·
case study · earnings-day market-reaction study) on a 9-company watchlist (tech + bank/retail/energy/
healthcare), built for **$0**. Latest eval (n=9): guidance / tone / metrics 100%, themes F1 ~0.95;
positive-lean calls averaged +3.3% on the day vs −1.4% neutral (signal has directional information).
Results: [CASE_STUDY.md](CASE_STUDY.md).

## Layout
```
engine/          # the pipeline package
  schema.py      # EarningsSignal — the locked output contract (§3)
  taxonomy.py    # controlled vocabulary for key_themes (§4)
  extract.py     # Claude tool-use extractor, Haiku→Sonnet escalation (§8)
  confidence.py  # confidence derivation + review routing (§6)
  fetch.py       # transcript loader (local file / FMP)
scripts/
  run_phase1.py  # end-to-end: transcript -> EarningsSignal (JSON)
tests/           # offline schema/taxonomy tests
data/
  transcripts/   # raw transcripts (gitignored — licensed)
  goldset/       # hand-labeled eval set (Phase 3)
  output/        # extracted signals (gitignored)
```

## Quickstart
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill ANTHROPIC_API_KEY (+ FMP_API_KEY to fetch live)

# Drop a transcript at data/transcripts/NVDA_Q1_FY2027.txt, then:
python scripts/run_phase1.py
```

## Tests (offline, no API key)
```bash
pytest -q
```
