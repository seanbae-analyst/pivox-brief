"""Filing document text for the qualitative read (Layer 2) — fetch + section-slice.

Pulls a filing's primary document from SEC EDGAR (``engine.edgar.fetch_text``) and reduces
it to the section a reader needs: 10-K **Item 1A** (risk factors) or 10-Q/10-K **MD&A**.
The HTML→text reduction is deliberately dependency-free (regex, no bs4) — the output feeds
a structured extraction, not display, so byte-perfect fidelity isn't required.

Pure functions (``html_to_text`` / ``slice_section`` / ``risk_factors`` / ``mda``) are split
from the single I/O call so they unit-test offline against a fixture. Only official EDGAR
documents are fetched; we derive structured facts and never republish the text (§1).
"""

from __future__ import annotations

import html as _html
import re

from engine import edgar

_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BLOCK_END = re.compile(r"</(p|div|tr|h[1-6]|li|table)>", re.IGNORECASE)
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_INLINE_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n\s*")


def html_to_text(html: str) -> str:
    """Strip an EDGAR HTML document to readable text (no external deps)."""
    s = _SCRIPT_STYLE.sub(" ", html)
    s = _BR.sub("\n", s)
    s = _BLOCK_END.sub("\n", s)
    s = _TAG.sub(" ", s)
    s = _html.unescape(s)
    s = _INLINE_WS.sub(" ", s)
    s = _BLANK_LINES.sub("\n\n", s)
    return s.strip()


def slice_section(text: str, start_patterns: list[str], end_patterns: list[str],
                  max_chars: int = 60000, key=len) -> str:
    """Text from a section header to the next item boundary.

    A filing names each item several times — table of contents, cross-references, and the
    real section — so we consider EVERY start match and keep the highest-scoring slice.
    ``key`` scores a candidate chunk; default ``len`` (the real section runs longest), but
    callers override it (e.g. risk-language density) when length alone is ambiguous — a huge
    section can hit ``max_chars`` and tie with a cross-reference. Returns '' if no start found.
    """
    starts = []
    for pat in start_patterns:
        starts += list(re.finditer(pat, text, re.IGNORECASE))
    if not starts:
        return ""

    best, best_score = "", float("-inf")
    for m in sorted(starts, key=lambda x: x.start()):
        lo, after = m.start(), m.end()  # end-search anchored just past the header
        hi = len(text)
        for pat in end_patterns:
            em = re.search(pat, text[after:], re.IGNORECASE)
            if em:
                hi = min(hi, after + em.start())
        chunk = text[lo:hi].strip()[:max_chars]
        score = key(chunk)
        if score > best_score:
            best, best_score = chunk, score
    return best


_RISK_WORDS = re.compile(
    r"\b(risk|adversely|could|harm|uncertain|fail|decline|unable|litigation|competit|materi)\w*",
    re.IGNORECASE,
)


def _risk_density(chunk: str) -> int:
    """Count risk-language hits in the section head — the real Item 1A is dense with it;
    a cross-reference followed by financial tables / MD&A prose is not."""
    return len(_RISK_WORDS.findall(chunk[:5000]))


def risk_factors(text: str, max_chars: int = 60000) -> str:
    """10-K Item 1A (Risk Factors), up to Item 1B / Item 2.

    Scored by risk-language density (not length): NVDA-class issuers have a >60k-char
    section that hits the cap and would tie with cross-references on length, but a
    cross-ref's head is financial-table prose with little risk vocabulary."""
    return slice_section(
        text,
        [r"item\s*1a\.?\s*[\.\-—:]*\s*risk\s+factors(?!\s*[,\"”’])"],
        [r"item\s*1b\.?", r"item\s*2\.?\s*propert", r"item\s*7\.?\s*management"],
        max_chars,
        key=_risk_density,
    )


def mda(text: str, max_chars: int = 50000) -> str:
    """Management's Discussion & Analysis (Item 7 in 10-K / Item 2 in 10-Q)."""
    return slice_section(
        text,
        [r"management'?.{0,3}s\s+discussion\s+and\s+analysis"],
        [r"item\s*3\.?\s*quantitative", r"item\s*7a\.?\s*quantitative",
         r"item\s*4\.?\s*controls", r"quantitative\s+and\s+qualitative\s+disclosures"],
        max_chars,
    )


def fetch_filing_text(url: str) -> str:
    """Fetch + reduce an EDGAR filing document to plain text (the one I/O entry)."""
    return html_to_text(edgar.fetch_text(url))
