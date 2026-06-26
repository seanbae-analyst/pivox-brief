# Pivox Brief — Strategy: from data aggregator to a refined-signal research engine

> Written 2026-06-25. Supersedes the "research pack" framing in RESEARCH_PACK_PLAN.md as the
> product north star. PROJECT.md remains the earnings-engine SoT; DATA_SOURCES.md the legal posture.

## The honest problem with where we are

v1/v2 **aggregate** official data — financials (XBRL), filings, insider (Form 4), qualitative
themes, a coverage manifest. It's clean, $0, and well-built. But **aggregation is not
innovative.** Every free site (Yahoo, stockanalysis.com, roic.ai) shows fundamentals; SEC EDGAR
itself shows the filings. Pulling the same facts onto one page is *convenient*, not
*differentiated*. That's the gap: a researcher looks at it and thinks "I've seen this."

## The reframe

**Raw data is a commodity. The product is the PROCESSING layer.**

The value is not "here is the data." It is: *"here is the signal an analyst would spend hours
assembling by hand — derived from official filings, structured so you can research on top."* We
never tell the user what to do (that is advice, and forbidden — §10). We hand them refined inputs
and the open questions, and they judge.

## The innovation thesis — 3 processing dimensions aggregators drop

A static aggregator shows a **snapshot**. The signal lives in the dimensions free tools skip:

1. **Δ Time — what *changed*.** Risk-factor deltas (risks added/removed YoY), tone/theme
   trajectory across quarters, guidance-vs-actual, accrual & margin inflections. *Markets move on
   the delta, not the level.* A static P/E tells you nothing a screener can't; "risk factors added
   3 new China-export clauses this year" is signal.
2. **Peer-relative — *where* it sits.** Auto peer set (same SIC code) → percentile rank on each
   factor. "25% gross margin" is meaningless alone; "12th percentile in its industry" is signal.
3. **Behavioral — *who* is acting.** Insider cluster-buys vs routine vesting, 13F accumulation /
   distribution, disclosure-cadence spikes. Behavior leads disclosure.

And the layer that ties them together:

4. **Research scaffold — *where to look*.** Synthesize the above into "the N things that will move
   this stock + the data on each + what's unresolved." Not a verdict — a *map for your research*.

## Every stock-affecting domain × the processing that makes it research-grade

| Domain | Raw source ($0 / official) | The PROCESSING (the value-add) |
|---|---|---|
| Fundamentals | SEC XBRL | earnings-quality flags (accruals, cash-conversion), margin/growth **trajectory**, peer **percentiles** |
| Disclosures | 10-K / 10-Q / 8-K | **risk-factor delta** (YoY), 8-K event cadence, MD&A theme extraction |
| Management signal | filing text | tone/theme + **trajectory across quarters**, guidance-vs-actual |
| Insider / ownership | Form 4 / 13D-G / 13F | **cluster-buy detection**, buy/sell ratio, smart-money accumulation (13F Δ) |
| Capital structure | XBRL | buyback/dilution **trajectory**, debt-maturity timing |
| Macro exposure | filings (FX/rate/commodity/geo mentions) × FRED | "rate-sensitive — and rates just moved" **linkage** |
| Catalysts | filing calendar + 8-K | upcoming events, what to watch next |
| (KR) investor flows | — | 🟡 documented gap — no clean free API (DATA_SOURCES.md) |

## The moat *is* the constraints

`$0 + official-only + descriptive-not-advice + citable`. Not a limitation — the reason it is
defensible:

- **Bloomberg / FactSet** cost ~$24k/yr and bury the signal in a firehose. We surface the *derived*
  signal for $0.
- **Free sites** give raw data, zero processing. We process.
- Every number links to its **SEC / DART source** — auditable, unlike opaque third-party "scores."
- **"We don't advise — we scaffold *your* research"** is simultaneously legal-clean *and* the real
  value proposition for a serious researcher.

## The one rule: descriptive, never a verdict

Every output is an **observation + its data + its source**, never a recommendation.

> ✅ "Net income exceeded operating cash flow by 18% (accrual gap; 88th percentile vs 9 SIC peers)."
> ❌ "Earnings quality is poor — avoid."

The user draws the conclusion. This keeps it inside §10 (not investment advice) *and* makes it a
genuine research tool rather than a signal-seller.

## Roadmap

- **Wave 1 ✅ done:** earnings-quality flags · risk-factor delta · insider patterns.
  (Δ-time + behavioral processing on data we already pull — fastest path to "this is different.")
- **Wave 2 ✅ done:** peer-relative percentiles (SIC peer set) · macro-exposure tags × FRED.
- **Wave 3 ✅ done:** the **research-scaffold** synthesis ("N things + open questions",
  `engine/scaffold.py`) · **8-K event cadence** (`engine/cadence.py` — disclosure rhythm + event
  mix, Δ-time) · **management-tone trajectory across quarters** (`engine/tone_trajectory.py` —
  Loughran-McDonald lexical density on MD&A, auditable, descriptive).
  - **Documented gaps (honest, not built):** *13F institutional flow Δ* — structurally hard for a
    keyless tool (needs a CUSIP reverse-index across thousands of 13F filers; no per-issuer EDGAR
    index) → kept as a 🟡 coverage gap, not scraped. *Guidance-vs-actual* — guidance figures live in
    8-K exhibit text (EX-99.1), fragile to parse $0 → deferred; the qualitative read still captures
    guidance *direction* where given. (Both surfaced in the coverage manifest.)

## Bottom line

Pivox Brief becomes **"the refined-signal layer over official filings"** — the diff / peer /
behavioral processing that turns public disclosures into research-ready signal, $0 and citable.
**The innovation is the processing, not the aggregation.**
