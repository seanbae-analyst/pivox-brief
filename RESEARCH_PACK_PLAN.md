# Research Pack — design & handoff (next session)

## Vision
Search a ticker / company name → a one-page **research pack** of everything price-relevant,
in the right language (**KR stock → Korean, US stock → English**). A research *starting point*
for the analyst (the user decides) — not investment advice (§10).

## Legally-clean architecture (decided)
Lean on **official / public sources** so it passes a maximally-conservative bar (see
[DATA_SOURCES.md](DATA_SOURCES.md)). Honest correction: the first risk read was *practical*,
not *maximal* — a public repo is publication, KR/EU database rights exist, and yfinance is
ToS-gray. This plan reflects the conservative posture.

| Section | Clean source |
|---|---|
| Snapshot (name/exchange/price/52w/PE) | EDGAR (US) / DART (KR); price = yfinance (demo-labeled) |
| Financials trend (rev/margin/EPS, ~4Q) | **EDGAR XBRL** (US) / **DART** (KR) |
| Earnings read (guidance / risk factors) | EDGAR 8-K + 10-Q MD&A/risk (US) / DART (KR) |
| Price reaction / recent action | yfinance (demo-labeled, isolated) |
| News & catalysts | WebSearch — headline + link only (KR: Korean) |
| Risks / themes | from filings + news |

**Tradeoff (honest):** dropping transcripts (copyright) weakens the *call tone / Q&A* feature —
filings carry guidance/financials/risk but not the verbal call. Acceptable for the clean build.

## Verified this session
- ✅ **SEC EDGAR keyless ($0):** ticker→CIK (`company_tickers.json`), filings (`submissions`),
  financials (`xbrl/companyconcept`). Needs `User-Agent` header + ≤10 req/s.
- ⚠️ **DART needs a free API key — USER ACTION:** register at opendart.fss.or.kr, put
  `DART_API_KEY` in `.env`.

## Build steps (next session)
1. `engine/edgar.py` — ticker→CIK, latest 8-K/10-Q, XBRL financial facts (keyless + UA from env).
2. `engine/dart.py` — KR filings via Open DART (needs key).
3. Name/ticker resolution — EDGAR ticker map (US), DART corpCode (KR), WebSearch fallback.
4. `engine/research_pack.py` — assemble the sections above; choose language by exchange.
5. `scripts/research.py <TICKER|name>` — print/save the brief (KR or EN).
6. (optional) dashboard "stock pack" page.
7. Honor DATA_SOURCES.md: UA via env, rate-limit, no redistribution, news = link-only.

## Reuse what exists
The current engine feeds the pack: `schema`/`confidence` (the signal), `analysis`
(intelligence + market reaction), `evaluation` (quality), `prices` (reaction). 31 tests green.

## Resume here
Start at **step 1 (`engine/edgar.py`)**. Confirm the DART key with the user before step 2.
