"""Insider & large-holder activity — SEC EDGAR Form 4 (insider transactions) + 13D/G.

Insider open-market buys/sells (Form 4) and >5% stake filings (13D/G) are near-real-time,
high-signal price movers. Form 4 XML is parsed to a transaction summary (who, code, shares,
price, acquired/disposed); 13D/G are surfaced as dated links (filer/holdings live in varied
document formats). Official EDGAR data, derived facts only (§1).

Signal lives in the OPEN-MARKET trades — P (purchase) / S (sale); grants (A), tax withholding
(F), option exercises (M) and gifts (G) are routine. We keep them all but rank discretionary
trades first, so a reader sees real buying/selling at a glance (and an all-routine stream is
itself an honest "no discretionary activity" signal).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from engine import edgar

LARGE_HOLDER_FORMS = ("SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A")

TX_CODES = {
    "P": "Open-market purchase", "S": "Open-market sale", "A": "Grant/award",
    "D": "Disposition to issuer", "F": "Shares withheld for tax", "M": "Option exercise",
    "G": "Gift", "C": "Conversion", "X": "Option exercise", "J": "Other",
}
DISCRETIONARY = {"P", "S"}


def _txt(el, path):
    e = el.find(path)
    return e.text.strip() if (e is not None and e.text and e.text.strip()) else None


def _f(s):
    try:
        return float(s) if s not in (None, "") else None
    except ValueError:
        return None


def form4_raw_xml_url(f) -> str:
    """Machine-readable Form 4 XML URL — strip the XSL render subdir from the primary doc.
    primaryDocument is e.g. ``xslF345X06/wk-form4_123.xml``; the raw XML sits one dir up."""
    if f.url.endswith(f.primary_document):
        folder = f.url[: -len(f.primary_document)]
    else:
        folder = f.url.rsplit("/", 1)[0] + "/"
    return folder + f.primary_document.split("/")[-1]


def parse_form4(xml_text: str, url: str = "") -> list[dict]:
    """Parse a Form 4 ownership XML into non-derivative transaction dicts (one per transaction)."""
    root = ET.fromstring(xml_text)
    owner = _txt(root, ".//reportingOwner/reportingOwnerId/rptOwnerName") or "—"
    rels = []
    if _txt(root, ".//reportingOwnerRelationship/isDirector") in ("1", "true"):
        rels.append("Director")
    if _txt(root, ".//reportingOwnerRelationship/isOfficer") in ("1", "true"):
        rels.append(_txt(root, ".//reportingOwnerRelationship/officerTitle") or "Officer")
    if _txt(root, ".//reportingOwnerRelationship/isTenPercentOwner") in ("1", "true"):
        rels.append("10% owner")
    relationship = ", ".join(rels) or "—"

    out = []
    for t in root.findall(".//nonDerivativeTransaction"):
        code = _txt(t, "transactionCoding/transactionCode") or "?"
        shares = _f(_txt(t, "transactionAmounts/transactionShares/value"))
        price = _f(_txt(t, "transactionAmounts/transactionPricePerShare/value"))
        out.append({
            "owner": owner,
            "relationship": relationship,
            "date": _txt(t, "transactionDate/value"),
            "code": code,
            "code_label": TX_CODES.get(code, f"Code {code}"),
            "acquired_disposed": _txt(t, "transactionAmounts/transactionAcquiredDisposedCode/value") or "?",
            "shares": shares,
            "price": price,
            "value": round(shares * price, 0) if (shares and price) else None,
            "discretionary": code in DISCRETIONARY,
            "url": url,
        })
    return out


def insider_transactions(cik, max_filings: int = 10, max_tx: int = 8) -> list[dict]:
    """Fetch + parse recent Form 4s. Discretionary open-market trades (P/S) ranked first, then
    most-recent. ``max_filings`` bounds EDGAR fetches; ``max_tx`` bounds the returned list."""
    _, filings = edgar.company_filings(cik, forms=("4",), limit=max_filings)
    txs: list[dict] = []
    for f in filings:
        try:
            txs += parse_form4(edgar.fetch_text(form4_raw_xml_url(f)), url=f.url)
        except Exception:
            continue  # one malformed Form 4 never breaks the pack
    txs.sort(key=lambda t: t["date"] or "", reverse=True)      # recent first
    txs.sort(key=lambda t: 0 if t["discretionary"] else 1)     # stable → P/S float to the top
    return txs[:max_tx]


def large_holder_filings(cik, limit: int = 6) -> list[dict]:
    """Recent 13D/13G (>5% stakes) as dated links."""
    _, filings = edgar.company_filings(cik, forms=LARGE_HOLDER_FORMS, limit=limit)
    return [{"form": f.form, "filed": f.filing_date, "url": f.url} for f in filings]


def ownership_block(cik, max_filings: int = 10) -> dict:
    """Combined insider + large-holder activity for the research pack."""
    return {
        "insider_transactions": insider_transactions(cik, max_filings=max_filings),
        "large_holder_filings": large_holder_filings(cik),
    }
