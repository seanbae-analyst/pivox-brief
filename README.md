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

## Research Pack — search a ticker, get one page
Beyond the earnings engine, `pivox-brief` assembles a one-page **research pack** of the
price-relevant factors for a stock, in the right language (US → English, KR → Korean),
from **official sources only** — SEC EDGAR (keyless) and Open DART. See
[DATA_SOURCES.md](DATA_SOURCES.md) for the legal posture.

```bash
# US issuer (keyless; set EDGAR_USER_AGENT in .env to declare your identity to SEC)
python scripts/research.py NVDA              # or "nvidia" — resolves names too
python scripts/research.py AAPL --save       # also writes data/output/AAPL.research.md

# Korean issuer (free DART_API_KEY in .env; register at opendart.fss.or.kr)
python scripts/research.py 삼성전자           # KR stock, brief in Korean

# Static stock-pack web page — no backend, GitHub-Pages-ready
python scripts/build_pack_page.py NVDA AAPL AMD   # -> docs/pack.html
```

Each pack carries a snapshot, a quarterly financial trend (revenue, margins, EPS, YoY)
from XBRL, the **earnings read** (latest 8-K Item 2.02 release · 10-Q · 10-K risk
factors), recent filings labeled by what they cover, link-only news (§4), source links,
and the §10 disclaimer. A research *starting point* — not investment advice.

## Status
**Phases 0–6 + a stock-price layer** (schema · extraction · confidence routing · eval · dashboard ·
case study · earnings-day market-reaction study) on a 9-company watchlist (tech + bank/retail/energy/
healthcare), built for **$0**. Latest eval (n=9): guidance / tone / metrics 100%, themes F1 ~0.95;
positive-lean calls averaged +3.3% on the day vs −1.4% neutral (signal has directional information).
Results: [CASE_STUDY.md](CASE_STUDY.md).

## Layout
```
engine/                # the pipeline package
  schema.py            # EarningsSignal — the locked output contract (§3)
  taxonomy.py          # controlled vocabulary for key_themes (§4)
  extract.py           # Claude tool-use extractor, Haiku→Sonnet escalation (§8)
  confidence.py        # confidence derivation + review routing (§6)
  fetch.py             # transcript loader (local file / FMP)
  # --- research pack ---
  edgar.py             # SEC EDGAR (US): ticker/name -> CIK, filings, XBRL financials (keyless)
  dart.py              # Open DART (KR): corp_code, disclosures, financials (needs key)
  research_pack.py     # US pack assembly + Markdown render
  research_pack_kr.py  # KR pack assembly + Korean render
  news.py              # link-only news cache (§4)
  prices.py            # demo-labeled price snapshot + earnings-day reaction
scripts/
  run_phase1.py        # earnings engine: transcript -> EarningsSignal (JSON)
  research.py          # research pack: ticker/name -> one-page brief (US/EDGAR, KR/DART)
  build_pack_page.py   # static docs/pack.html (stock selector, data inlined)
  build_dashboard.py   # earnings-intelligence dashboard
tests/                 # offline tests (no API key, no network)
data/
  transcripts/         # raw transcripts (gitignored — licensed)
  goldset/             # hand-labeled eval set (Phase 3)
  output/              # extracted signals (gitignored)
  news/                # link-only headline cache per ticker (§4)
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
