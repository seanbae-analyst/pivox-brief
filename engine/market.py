"""Market-wide context — rate regime, yield curve, and speculative positioning.

FREE OFFICIAL sources only (consistent with DATA_SOURCES.md's conservative posture):
- US Treasury daily par yield curve   — keyless, public domain
- CFTC Commitments of Traders (legacy futures-only) — keyless, public
- FRED (St. Louis Fed)                — OPTIONAL, free API key (FRED_API_KEY in .env):
  VIX, high-yield credit spread, major indices, the broad dollar, unemployment, fed funds.

Deliberately NOT covered (licensed / proprietary): real-time quotes, options-implied
volatility, sell-side consensus / price targets / estimate revisions, and proprietary
retail-/social-sentiment scores. The pack names these blind spots rather than faking them.

`build_market_context()` is ticker-independent — it is baked once into the static page and
shown on every pack as a market backdrop. Every fetch degrades gracefully (returns partial
data, never raises), so a slow or unreachable source just drops its block.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import date, timedelta

import requests

_UA = {"User-Agent": "Mozilla/5.0 (compatible; pivox-brief/1.0; research-pack)"}
_TIMEOUT = 20


def _f(v) -> float | None:
    try:
        if v in (None, "", "."):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _treasury_curve() -> dict | None:
    """Latest US Treasury par yield curve (most-recent row of the year's daily CSV)."""
    yr = date.today().year
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/{yr}/all"
        f"?type=daily_treasury_yield_curve&field_tdr_date_value={yr}&page&_format=csv"
    )
    try:
        r = requests.get(url, headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(r.text)))
        if not rows:
            return None
        row = rows[0]  # CSV is sorted most-recent-first
        y2, y10, y3m = _f(row.get("2 Yr")), _f(row.get("10 Yr")), _f(row.get("3 Mo"))
        spread = round(y10 - y2, 2) if (y10 is not None and y2 is not None) else None
        spread3m = round(y10 - y3m, 2) if (y10 is not None and y3m is not None) else None
        curve = None
        if spread is not None:
            curve = "inverted" if spread < 0 else ("flat" if spread < 0.20 else "upward")
        return {
            "as_of": row.get("Date"),
            "y3m": y3m, "y2": y2, "y10": y10, "y30": _f(row.get("30 Yr")),
            "spread_10y_2y": spread, "spread_10y_3m": spread3m, "curve": curve,
        }
    except Exception:
        return None


# (label, market_and_exchange_names LIKE pattern) — only markets the legacy futures-only
# report still updates weekly (rates/FX live under other CFTC reports → covered by the
# Treasury curve + FRED instead, not here).
_COT_MARKETS = [
    ("E-mini S&P 500", "E-MINI S&P 500 -%"),
    ("Gold", "GOLD - COMMODITY EXCHANGE%"),
]


def _cot_positioning() -> list[dict]:
    """Net non-commercial (speculative) positioning for a few market-mood futures."""
    base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
    cutoff = (date.today() - timedelta(days=150)).isoformat()  # drop stale / renamed contracts
    out: list[dict] = []
    for label, pat in _COT_MARKETS:
        try:
            params = {
                "$limit": 1,
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$where": f"market_and_exchange_names like '{pat}' AND report_date_as_yyyy_mm_dd > '{cutoff}'",
                "$select": (
                    "report_date_as_yyyy_mm_dd,noncomm_positions_long_all,"
                    "noncomm_positions_short_all,open_interest_all"
                ),
            }
            r = requests.get(base, params=params, headers=_UA, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if not data:
                continue
            row = data[0]
            lng = int(_f(row.get("noncomm_positions_long_all")) or 0)
            sht = int(_f(row.get("noncomm_positions_short_all")) or 0)
            net = lng - sht
            out.append({
                "market": label, "net": net, "long": lng, "short": sht,
                "oi": int(_f(row.get("open_interest_all")) or 0),
                "as_of": (row.get("report_date_as_yyyy_mm_dd") or "")[:10],
                "stance": "net long" if net >= 0 else "net short",
            })
        except Exception:
            continue
    return out


# (field, FRED series id, label, unit suffix)
_FRED_SERIES = [
    ("fed_funds", "DFF", "Fed funds", "%"),
    ("vix", "VIXCLS", "VIX", ""),
    ("hy_spread", "BAMLH0A0HYM2", "HY credit spread", "%"),
    ("spx", "SP500", "S&P 500", ""),
    ("nasdaq", "NASDAQCOM", "Nasdaq Comp", ""),
    ("dollar", "DTWEXBGS", "US dollar (broad)", ""),
    ("unrate", "UNRATE", "Unemployment", "%"),
]


def _fred() -> dict | None:
    """Optional macro band — only if FRED_API_KEY is set (free key, instant)."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None
    macro: dict = {}
    for fld, sid, label, unit in _FRED_SERIES:
        try:
            r = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": sid, "api_key": key, "file_type": "json",
                        "sort_order": "desc", "limit": 1},
                headers=_UA, timeout=_TIMEOUT,
            )
            r.raise_for_status()
            obs = r.json().get("observations", [])
            val = _f(obs[0].get("value")) if obs else None
            if val is not None:
                macro[fld] = {"value": val, "as_of": obs[0]["date"], "label": label, "unit": unit}
        except Exception:
            continue
    return macro or None


def build_market_context() -> dict:
    """Assemble the ticker-independent market backdrop. Never raises."""
    rates = _treasury_curve()
    positioning = _cot_positioning()
    macro = _fred()
    sources = [
        "US Treasury — Daily Par Yield Curve (home.treasury.gov)",
        "CFTC Commitments of Traders, legacy futures-only (publicreporting.cftc.gov)",
    ]
    if macro:
        sources.append("FRED — Federal Reserve Bank of St. Louis (fred.stlouisfed.org)")
    return {
        "as_of": (rates or {}).get("as_of") or str(date.today()),
        "rates": rates,
        "positioning": positioning,
        "macro": macro,
        "macro_available": macro is not None,
        "sources": sources,
        "out_of_reach": (
            "Real-time quotes, options-implied vol, sell-side consensus / price targets, "
            "and proprietary sentiment scores are licensed — not shown."
        ),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_market_context(), indent=2, ensure_ascii=False))
