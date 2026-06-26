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
import re
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# 1–12 chars, ticker-shaped — reject junk before doing any (expensive) EDGAR work.
_VALID_TICKER = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")
# KR query: a 6-digit KRX code or a Korean (Hangul) name → routed to Open DART.
_HANGUL = re.compile(r"[가-힣]")
_VALID_KR = re.compile(r"^[가-힣A-Za-z0-9 ().]{1,20}$")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.research_pack import build_us_pack, to_page_dict  # noqa: E402

_SEARCH_NOTE = (
    "Searched ticker — live SEC EDGAR fundamentals, filings, insider activity & coverage. "
    "Price-based multiples and the AI Signal read are shown on featured tickers."
)
_SEARCH_NOTE_KR = (
    "검색한 종목 — Open DART 공식 공시 기반 재무·공시. "
    "가격·밸류에이션 배수와 AI 시그널은 featured 종목에 표시됩니다."
)


def research(ticker: str) -> dict | None:
    """Live EDGAR pack for an arbitrary US ticker (no demo price; cloud-safe).

    Skips the risk-factor delta (two full 10-Ks) and the tone trajectory (several full 10-Q MD&As)
    — both too slow for a request — and caps the insider Form-4 fetches (a per-request fan-out /
    SEC-rate-limit risk on a public endpoint). Earnings-quality flags + 8-K cadence stay (cheap:
    already-fetched XBRL / one submissions read).
    """
    pack = build_us_pack(ticker, with_price=False, with_risk_delta=False,
                         with_tone_trajectory=False, insider_max_filings=5)
    if pack is None:
        return None
    d = to_page_dict(pack)
    d["searched"] = True
    d["search_note"] = _SEARCH_NOTE
    from engine.analysts import analyst_consensus
    d["analysts"] = analyst_consensus(ticker)   # gray-zone: sell-side via Finnhub (key-gated, graceful)
    return d


def research_kr(query: str) -> dict | None:
    """Live Open DART pack for a KR issuer (6-digit code or Korean name). Needs DART_API_KEY."""
    from datetime import date
    from engine.research_pack_kr import build_kr_pack, to_kr_page_dict
    pack = build_kr_pack(query, year=date.today().year - 1)
    if pack is None:
        return None
    d = to_kr_page_dict(pack)
    d["searched"] = True
    d["search_note"] = _SEARCH_NOTE_KR
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
        try:
            query = parse_qs(urlparse(self.path).query)
        except Exception:
            return self._send(400, {"error": "bad request"})
        ticker = (query.get("ticker", [""])[0] or "").strip()
        if not ticker:
            return self._send(400, {"error": "missing ?ticker= (e.g. /api/research?ticker=NVDA)"})
        # Route KR queries (6-digit KRX code or Korean name) to Open DART; everything else to EDGAR.
        if _HANGUL.search(ticker) or (ticker.isdigit() and len(ticker) == 6):
            if not _VALID_KR.match(ticker):
                return self._send(400, {"error": "invalid KR query — 6-digit code or Korean name"})
            try:
                result = research_kr(ticker)
            except Exception as exc:
                print(f"[research_kr] error for {ticker!r}: {exc}", file=sys.stderr)
                return self._send(502, {"error": "lookup failed"})
            if result is None:
                return self._send(404, {"error": "Open DART에서 조회되지 않는 종목입니다"})
            return self._send(200, result)
        if not _VALID_TICKER.match(ticker):
            return self._send(400, {"error": "invalid ticker — 1–12 chars, letters/digits/.- only"})
        try:
            result = research(ticker)
        except Exception as exc:  # log server-side; return a generic message (no internals leaked)
            print(f"[research] error for {ticker!r}: {exc}", file=sys.stderr)
            return self._send(502, {"error": "lookup failed"})
        if result is None:
            return self._send(404, {"error": "ticker did not resolve in SEC EDGAR (US issuers only)"})
        return self._send(200, result)
