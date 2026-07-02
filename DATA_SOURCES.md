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
| **FRED API** | rates, VIX, HY spread, stress indices | ✅ verified 2026-07-02 | Attribution required (footer credits FRED); may not imply St. Louis Fed endorsement — non-endorsement note added to web+email footers. |
| **alternative.me** (crypto F&G) | crypto sentiment component | ✅ verified 2026-07-02 | Attribution required "right next to the display" (their terms); commercial OK with credit. Credit added beside the F&G card. |
| **Finnhub** (analyst consensus) | sell-side rating distribution + targets | ⚠️ gray — verified 2026-07-02 | ToS: "strictly for personal use", no redistribution of data **or derived results** without written approval. Public display of the consensus card sits outside that. Card is labeled "via Finnhub"; worst realistic case = free key revoked. Decision: keep for the demo, drop or license before any public/commercial push. |
| **KIS OpenAPI** (투자자 수급) | KR foreign/retail net-flow aggregate | ⚠️ terms unverified | Official API (read-only), but the full ToS sits behind the portal login — redistribution clause unconfirmed (checked 2026-07-02, page not publicly fetchable). We publish only a derived 5-day aggregate (조 단위), not quotes. Verify the clause from a logged-in session before any commercial use. |
| **KRX investor flows** (외국인/기관 일별 순매매) | KR per-stock daily foreign / institutional net buy-sell | ⚠️ no clean API | See note below — the official KRX OPEN API does **not** expose investor-type flows; the only programmatic source is the gray `data.krx.co.kr` internal endpoint (what pykrx scrapes). Excluded by our posture pending a decision. |

## KR investor flows (외국인 매도) — researched 2026-06-23, decision pending

Korean per-stock daily investor-type net flows (foreign / institution / individual) are a
high-signal price driver and are **published for on-screen viewing** at the KRX Data
Marketplace. But there is **no clean, free, sanctioned programmatic API** for them:

- **Official KRX OPEN API** (`openapi.krx.co.kr`, requires a free key) — covers indices,
  stocks/ETF/bond/derivative **prices & trading**, but **has no investor-type flow endpoint**.
- **`data.krx.co.kr` `getJsonData.cmd`** — the only endpoint that returns investor flows. It is
  KRX's *undocumented internal* endpoint (exactly what **pykrx** scrapes), which this project
  treats as **ToS-gray / excluded** (see pykrx note).
- **공공데이터포털 (data.go.kr)** — KRX-sourced datasets are listing/price info, not per-stock
  investor flows.

**Decision for the operator** (do not auto-enable): (a) accept the gray `data.krx.co.kr` route
for *personal/dev only*, behind an explicit default-OFF flag and never redistributed; (b) license
a market-data vendor that carries KR flows; or (c) keep 외국인/기관 flow as a **documented 🟡 gap**
in the coverage manifest (honest "we don't see this for free"). Until chosen, the KR pack names
it as a blind spot rather than crossing the posture.

## What's in the repo
- **Committed (derived/factual):** `EarningsSignal` JSON, goldset labels, `reactions.json`,
  the dashboard, docs, `SOURCES.md`.
- **Not committed (copyright/intermediate):** raw transcripts (`data/transcripts/*.txt`), drafts.
