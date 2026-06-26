"""Peer comparison — same-sector US issuers, same headline metrics, side by side.

Auto peer discovery from SIC isn't cleanly available keyless, so the peer set is a small
curated map. Each peer is a LIGHT EDGAR pull (XBRL financials only — no filings / insider /
price), memoised within a build so a pack shows 'how does this name stack up' without a
heavy per-peer fetch. US (SEC EDGAR) only for now; KR cross-border peers (DART + FX
normalisation) are a separate step.
"""

from __future__ import annotations

from engine.research_pack import build_us_pack, to_page_dict

# Subject ticker -> a few closest same-sector US peers (10-K/XBRL filers).
_PEER_MAP: dict[str, list[str]] = {
    "NVDA": ["AMD", "AVGO", "INTC"],
    "AMD": ["NVDA", "AVGO", "INTC"],
    "AVGO": ["NVDA", "AMD", "QCOM"],
    "INTC": ["NVDA", "AMD", "AVGO"],
    "MU": ["WDC", "STX", "NVDA"],        # memory/storage + the AI-memory demand pull
    "AAPL": ["MSFT", "GOOGL", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "AMZN"],
    "GOOGL": ["MSFT", "META", "AMZN"],
}

_CACHE: dict[str, dict | None] = {}


def _snapshot(tk: str) -> dict | None:
    tk = tk.upper()
    if tk in _CACHE:
        return _CACHE[tk]
    snap = None
    try:
        pack = build_us_pack(tk, with_price=False, with_risk_delta=False,
                             with_tone_trajectory=False, insider_max_filings=0)
        if pack is not None:
            d = to_page_dict(pack)
            trend = d.get("trend") or []
            last = trend[-1] if trend else {}
            prof = ((d.get("quant") or {}).get("profitability")) or {}
            snap = {
                "ticker": d.get("ticker") or tk,
                "name": d.get("name"),
                "period": last.get("period"),
                "revenue": last.get("revenue"),
                "revenue_yoy_pct": last.get("revenue_yoy_pct"),
                "gross_margin": last.get("gross_margin"),
                "net_margin": last.get("net_margin"),
                "roe_pct": prof.get("roe_pct"),
            }
    except Exception:
        snap = None
    _CACHE[tk] = snap
    return snap


def peers_for(ticker: str | None) -> list[dict] | None:
    """Light same-sector peer snapshots for a US ticker, or None if unmapped/unresolved."""
    names = _PEER_MAP.get((ticker or "").upper())
    if not names:
        return None
    rows = [s for s in (_snapshot(p) for p in names) if s]
    return rows or None
