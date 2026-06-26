"""Sell-side analyst consensus — the deliberately GRAY-ZONE layer.

Unlike the rest of the pack (SEC EDGAR / Open DART / CFTC / US Treasury — primary official
sources), analyst ratings & price targets are aggregated sell-side opinion redistributed by a
data vendor. We surface them via Finnhub's free tier (FINNHUB_API_KEY) and label them clearly
as third-party opinion, descriptive — not our recommendation, and not a primary filing.

Free tier reliably serves recommendation trends (buy/hold/sell counts); the price-target
endpoint may require a paid plan, so it degrades gracefully (omitted if unavailable).
Returns None when no key is set or nothing resolves, so the card simply doesn't render.
"""

from __future__ import annotations

import os

import requests

_BASE = "https://finnhub.io/api/v1"
_TIMEOUT = 15
# (field, display) in conventional best→worst order
_BUCKETS = [("strongBuy", "Strong Buy"), ("buy", "Buy"), ("hold", "Hold"),
            ("sell", "Sell"), ("strongSell", "Strong Sell")]
_WEIGHT = {"strongBuy": 5, "buy": 4, "hold": 3, "sell": 2, "strongSell": 1}


def _dist(row: dict) -> dict:
    return {f: int(row.get(f) or 0) for f, _ in _BUCKETS}


def analyst_consensus(ticker: str) -> dict | None:
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        return None
    sym = (ticker or "").upper()
    try:
        r = requests.get(f"{_BASE}/stock/recommendation",
                         params={"symbol": sym, "token": key}, timeout=_TIMEOUT)
        r.raise_for_status()
        rec = r.json()
        if not isinstance(rec, list) or not rec:
            return None
        latest = rec[0]                      # newest period first
        dist = _dist(latest)
        total = sum(dist.values())
        if total == 0:
            return None
        score = sum(dist[f] * _WEIGHT[f] for f, _ in _BUCKETS) / total
        consensus = "Buy-leaning" if score >= 3.5 else ("Hold" if score >= 2.5 else "Sell-leaning")
        prior = rec[1] if len(rec) > 1 else None
        out = {
            "period": latest.get("period"),
            "distribution": dist,
            "buckets": [[d, f] for f, d in _BUCKETS],   # display order/labels for the renderer
            "total": total,
            "score": round(score, 2),
            "consensus": consensus,
            "prior": {"period": prior.get("period"), "distribution": _dist(prior)} if prior else None,
            "source": "Finnhub — aggregated sell-side recommendation trends",
        }
        # Price target — graceful (often a paid endpoint on the free tier)
        try:
            pt = requests.get(f"{_BASE}/stock/price-target",
                              params={"symbol": sym, "token": key}, timeout=_TIMEOUT)
            if pt.ok:
                j = pt.json() or {}
                if j.get("targetMean"):
                    out["target"] = {
                        "mean": j.get("targetMean"), "high": j.get("targetHigh"),
                        "low": j.get("targetLow"), "median": j.get("targetMedian"),
                        "as_of": j.get("lastUpdated"),
                    }
        except Exception:
            pass
        return out
    except Exception:
        return None
