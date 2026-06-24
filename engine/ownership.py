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


def _fetch_insider_txs(cik, max_filings: int = 20) -> list[dict]:
    """Parse the last ``max_filings`` Form 4s into a flat transaction list (one malformed
    filing never breaks the pack)."""
    _, filings = edgar.company_filings(cik, forms=("4",), limit=max_filings)
    txs: list[dict] = []
    for f in filings:
        try:
            txs += parse_form4(edgar.fetch_text(form4_raw_xml_url(f)), url=f.url)
        except Exception:
            continue
    return txs


def _rank(txs: list[dict], max_tx: int = 8) -> list[dict]:
    """Discretionary open-market trades (P/S) first, then most-recent."""
    ranked = sorted(txs, key=lambda t: t["date"] or "", reverse=True)
    ranked.sort(key=lambda t: 0 if t["discretionary"] else 1)
    return ranked[:max_tx]


def insider_transactions(cik, max_filings: int = 10, max_tx: int = 8) -> list[dict]:
    """Recent insider transactions, ranked (public API kept for callers/tests)."""
    return _rank(_fetch_insider_txs(cik, max_filings), max_tx)


def _usd(v: float) -> str:
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v:,.0f}"


def insider_pattern(txs: list[dict]) -> dict:
    """Refine a Form 4 transaction list into a DESCRIPTIVE behavioral signal (STRATEGY.md):
    open-market buys vs sells, how many distinct insiders (cluster), net discretionary value,
    and how much is routine (grants/tax/option). Never a verdict — the reader judges (§10)."""
    P = [t for t in txs if t["code"] == "P"]
    S = [t for t in txs if t["code"] == "S"]
    routine = [t for t in txs if t["code"] in ("F", "M", "A", "G", "C", "X")]
    buyers = sorted({t["owner"] for t in P})
    sellers = sorted({t["owner"] for t in S})
    buy_val = sum(t["value"] or 0 for t in P)
    sell_val = sum(t["value"] or 0 for t in S)
    dates = [t["date"] for t in txs if t["date"]]

    obs = []
    if P:
        obs.append(f"{len(P)} open-market buy(s) by {len(buyers)} insider(s) (~{_usd(buy_val)})")
    if S:
        obs.append(f"{len(S)} open-market sale(s) by {len(sellers)} insider(s) (~{_usd(sell_val)})")
    if not P and not S:
        obs.append(f"no discretionary open-market trades — only routine grants/tax/option ({len(routine)})")

    return {
        "open_market_buys": len(P),
        "open_market_sells": len(S),
        "buyers": buyers,
        "sellers": sellers,
        "buy_value": round(buy_val, 0),
        "sell_value": round(sell_val, 0),
        "net_discretionary_value": round(buy_val - sell_val, 0),
        "cluster_buy": len(buyers) >= 2,            # several insiders buying at once = notable
        "routine_count": len(routine),
        "window_filings": len(txs),
        "window_dates": [min(dates), max(dates)] if dates else [],
        "observation": ("Across the most recent " + str(len(txs)) + " Form 4 transactions: "
                        + "; ".join(obs) + "."),
    }


def large_holder_filings(cik, limit: int = 6) -> list[dict]:
    """Recent 13D/13G (>5% stakes) as dated links."""
    _, filings = edgar.company_filings(cik, forms=LARGE_HOLDER_FORMS, limit=limit)
    return [{"form": f.form, "filed": f.filing_date, "url": f.url} for f in filings]


def ownership_block(cik, max_filings: int = 20) -> dict:
    """Insider activity (ranked display list + behavioral pattern) + large-holder filings.
    Fetches the Form 4 batch once and derives both views from it."""
    txs = _fetch_insider_txs(cik, max_filings)
    return {
        "insider_transactions": _rank(txs, max_tx=8),
        "insider_pattern": insider_pattern(txs),
        "large_holder_filings": large_holder_filings(cik),
    }
