# Data sources & legal posture

> **Not legal advice** (the author is not a lawyer). This documents the project's
> conservative data-handling posture for a **personal research / portfolio** tool.
> Verify each source's current ToS and get legal review before any commercial or
> public-product use.

## Principles
- **Facts vs expression.** Numeric facts (prices, revenue, guidance direction) are
  generally not copyrightable — but (a) **databases/compilations can be protected**
  (KR Copyright Act §93 database-maker right; EU sui generis DB right) and (b) a
  site's **Terms of Service** can restrict access even to facts. "Facts are free" is
  not a blanket safe harbor.
- **Personal/research vs public/commercial.** A public GitHub repo or hosted page is
  *publication*, not private use — a higher bar than personal research.
- **Redistribution is the main risk.** We never republish third-party copyrighted
  text; we publish only our own derived facts/analysis + links to sources.

## Rules we follow
1. **No redistribution of copyrighted text.** Raw transcripts and article bodies are
   gitignored; only derived structured facts + provenance links are committed.
2. **Prefer official / public sources** (SEC EDGAR, DART) over scraping.
3. **Identify + rate-limit** automated access (declared User-Agent, ≤ provider limits).
4. **News:** headline + link + short factual summary only — never full article text.
5. **Prices:** treated as a gray area (table below) — labeled demo-only; a public or
   commercial build must use a licensed market-data feed.
6. **Not investment advice** — descriptive/analytical only (§10).

## Sources
| Source | Used for | Status | Posture |
|--------|----------|--------|---------|
| **SEC EDGAR** (US) | US financials, filings (8-K/10-Q/10-K), risk factors | ✅ verified keyless ($0) | US govt disclosure system; free programmatic access with a User-Agent + ≤10 req/s. Cleanest US source. |
| **DART Open API** (KR) | KR financials, disclosures | ⚠️ needs free API key | FSS official open-data API. Register at opendart.fss.or.kr → set `DART_API_KEY`. Cleanest KR source. |
| **yfinance / Yahoo** | prices, reaction, quick financials | ⚠️ gray | Unofficial scraper; Yahoo ToS restricts automated/commercial use. **Demo/personal only**; replace with a licensed feed for public/commercial. |
| **The Motley Fool** (transcripts) | current 9-company earnings read | ⚠️ copyrighted | Transcripts are copyrighted ("no reproduction"). We extract **facts only**; raw text gitignored. The clean research-pack path drops transcript dependence (uses EDGAR/DART filings). |
| **WebSearch** | finding sources, headlines | ✅ low | Discovery + headline/link; no body reproduction. |
| **FMP** | (optional) financials | licensed API | Use within their terms; redistribution per their license. |

## What's in the repo
- **Committed (derived/factual):** `EarningsSignal` JSON, goldset labels, `reactions.json`,
  the dashboard, docs, `SOURCES.md`.
- **Not committed (copyright/intermediate):** raw transcripts (`data/transcripts/*.txt`), drafts.
