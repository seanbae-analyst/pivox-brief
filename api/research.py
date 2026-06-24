"""Serverless search endpoint — GET /api/research?ticker=NVDA  (Vercel Python function).

Powers the hybrid page's "search any ticker" box: featured tickers are baked into the
static page (full pack incl. price multiples + AI Signal read); ANY other US issuer is
fetched live here from SEC EDGAR and returned in the same shape the frontend renders.

Honest degradation for searched tickers (documented in DATA_SOURCES.md / the page note):
- ✅ financial trend, margins, ROE, balance-sheet health, capital return, filings, insider
  (Form 4) + 13D/G, coverage manifest — all live from EDGAR (works from cloud IPs).
- ⚠️ NO price-based multiples (market cap / P/E / P/S / yields / technicals): those need the
  demo price feed (yfinance), which is blocked from cloud IPs — so build_us_pack runs with
  with_price=False here.
- ⚠️ AI Signal read (qualitative) only if a cached block exists (featured tickers); the $0
  extraction path is Claude-in-session, not this stateless function.

Reuses the exact engine + to_page_dict shape, so searched and featured tickers render
identically. Set EDGAR_USER_AGENT in the deployment env (SEC fair-access).
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.research_pack import build_us_pack, to_page_dict  # noqa: E402

_SEARCH_NOTE = (
    "Searched ticker — live SEC EDGAR fundamentals, filings, insider activity & coverage. "
    "Price-based multiples and the AI Signal read are shown on featured tickers."
)


def research(ticker: str) -> dict | None:
    """Live EDGAR pack for an arbitrary US ticker (no demo price; cloud-safe)."""
    pack = build_us_pack(ticker, with_price=False)
    if pack is None:
        return None
    d = to_page_dict(pack)
    d["searched"] = True
    d["search_note"] = _SEARCH_NOTE
    return d


class handler(BaseHTTPRequestHandler):  # Vercel Python entrypoint (class named `handler`)
    def _send(self, code: int, body: dict) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")  # static page may live on another origin
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Cache-Control", "public, max-age=900")  # 15-min edge cache
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:  # CORS preflight
        self._send(204, {})

    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        ticker = (query.get("ticker", [""])[0] or "").strip()
        if not ticker:
            return self._send(400, {"error": "missing ?ticker= (e.g. /api/research?ticker=NVDA)"})
        try:
            result = research(ticker)
        except Exception as exc:  # never leak a stack trace to the client
            return self._send(502, {"error": f"lookup failed for '{ticker}': {exc}"})
        if result is None:
            return self._send(404, {"error": f"'{ticker}' did not resolve in SEC EDGAR (US issuers only here)."})
        return self._send(200, result)
