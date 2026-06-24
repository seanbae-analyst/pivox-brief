"""Risk-factor delta — what changed in 10-K Item 1A year over year (STRATEGY.md, Δ-time).

Diffs the "Risk Factors Summary" one-liners of the two most recent 10-Ks: risks ADDED this year
and risks REMOVED. New risk language is a researched signal — a company doesn't add an
export-control or customer-concentration clause for nothing. DESCRIPTIVE: we report what changed
and link both filings; the reader judges (§10). Official EDGAR via engine.filings, derived facts only.

Header matching is fuzzy on purpose (wording drifts year to year): two risk lines are "the same"
when their word sets overlap above a threshold, so only genuinely new/dropped risks surface.
"""

from __future__ import annotations

import re

from engine import edgar, filings

_RISK_HINT = re.compile(
    r"\b(could|may|might|adversely|harm|fail|unable|depend|risk|uncertain|decline|disrupt|loss|"
    r"impair|liabilit|violat|breach|competit|subject)\w*", re.IGNORECASE)
_SUMMARY = re.compile(r"risk factors?\s+summary|summary of risk factors", re.IGNORECASE)
_CATEGORY = re.compile(r"^\s*risks?\s+(related\s+to|associated\s+with)", re.IGNORECASE)


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z]{4,}", s.lower()))


def _similar(a: str, b: str) -> float:
    """Jaccard overlap of significant words — robust to minor wording drift."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def extract_risk_headers(item1a: str, max_headers: int = 50) -> list[str]:
    """Pull the one-line risk statements from the 'Risk Factors Summary' block of an Item 1A."""
    m = _SUMMARY.search(item1a)
    region = item1a[m.end():] if m else item1a
    # the summary ends where the detailed section restarts (a bare "Risk Factors" heading)
    restart = re.search(r"\n\s*risk factors\s*\n", region[200:], re.IGNORECASE)
    if restart:
        region = region[: restart.start() + 200]
    region = region[:14000]

    heads: list[str] = []
    for raw in region.split("\n"):
        ln = raw.strip(" \t•▪◦-–—*·")
        if not (25 <= len(ln) <= 240):
            continue
        if _CATEGORY.match(ln) or _SUMMARY.search(ln):
            continue
        if not _RISK_HINT.search(ln):
            continue
        if not any(_similar(ln, h) >= 0.85 for h in heads):  # dedupe near-identical
            heads.append(ln)
        if len(heads) >= max_headers:
            break
    return heads


def diff_risks(current: list[str], prior: list[str], threshold: float = 0.5) -> dict:
    """Risks present this year with no close prior match = added; the reverse = removed."""
    added = [c for c in current if max((_similar(c, p) for p in prior), default=0.0) < threshold]
    removed = [p for p in prior if max((_similar(p, c) for c in current), default=0.0) < threshold]
    return {"added": added, "removed": removed}


def risk_delta(cik) -> dict | None:
    """Year-over-year Item 1A risk delta from the two most recent 10-Ks. None if unavailable."""
    _, tenks = edgar.company_filings(cik, forms=("10-K",), limit=3)
    if len(tenks) < 2:
        return None
    cur, pri = tenks[0], tenks[1]
    try:
        cur_h = extract_risk_headers(filings.risk_factors(filings.fetch_filing_text(cur.url)))
        pri_h = extract_risk_headers(filings.risk_factors(filings.fetch_filing_text(pri.url)))
    except Exception:
        return None
    if not cur_h or not pri_h:
        return None
    d = diff_risks(cur_h, pri_h)
    return {
        "added": d["added"],
        "removed": d["removed"],
        "current_count": len(cur_h),
        "prior_count": len(pri_h),
        "current_filing": {"filed": cur.filing_date, "url": cur.url},
        "prior_filing": {"filed": pri.filing_date, "url": pri.url},
    }
