"""Market psychology / sentiment layer — the broadest read we can build from FREE OFFICIAL
sources only (consistent with DATA_SOURCES.md's conservative posture). Ticker-independent;
baked once into the static page and shown on every pack as a market backdrop.

Signals (all keyless / public):
- Rate regime — US Treasury nominal + real (TIPS) par curves → level, slope (10y-2y, 10y-3m
  inversion = recession watch), and breakeven inflation (nominal - real) = market's inflation read.
- Cross-asset positioning — CFTC Commitments of Traders. The speculative crowd's net position in
  equities (S&P/Nasdaq/Russell), volatility (VIX), rates (Ultra 10Y), crypto (Bitcoin) and
  commodities (Gold/Crude), each scored as a 3-year **percentile** so crowded/extreme trades
  (contrarian psychology) stand out — not just the raw number.
- Regime read — a short descriptive synthesis (risk-on/off, complacency vs fear, crowded trades,
  recession watch). Descriptive, not advice.
- Optional FRED macro band (free API key) — VIX level, HY credit spread, indices, dollar, CPI, jobs.

Deliberately NOT covered (licensed / proprietary): real-time quotes, options-implied vol, sell-side
consensus / price targets / estimate revisions, proprietary retail-/social-sentiment scores. Each
fetch degrades gracefully (returns partial, never raises), so a slow source just drops its block.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import date, timedelta

import requests

_UA = {"User-Agent": "Mozilla/5.0 (compatible; pivox-brief/1.0; research-pack)"}
_TIMEOUT = 25

_TFF = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"     # Traders in Financial Futures
_LEGACY = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"  # legacy futures-only (commodities)


def _f(v) -> float | None:
    try:
        if v in (None, "", "."):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# ── Treasury curves (nominal + real → slope + breakeven inflation) ───────────────
def _treasury_csv(kind: str) -> dict | None:
    yr = date.today().year
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/{yr}/all?type={kind}&field_tdr_date_value={yr}&page&_format=csv"
    )
    try:
        r = requests.get(url, headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(r.text)))
        return rows[0] if rows else None  # most recent first
    except Exception:
        return None


def _rates() -> dict | None:
    nom = _treasury_csv("daily_treasury_yield_curve")
    if not nom:
        return None
    real = _treasury_csv("daily_treasury_real_yield_curve") or {}
    g = lambda row, k: _f(row.get(k))
    y3m, y2, y10, y30 = g(nom, "3 Mo"), g(nom, "2 Yr"), g(nom, "10 Yr"), g(nom, "30 Yr")
    real10 = g(real, "10 YR")
    spread_2 = round(y10 - y2, 2) if (y10 is not None and y2 is not None) else None
    spread_3m = round(y10 - y3m, 2) if (y10 is not None and y3m is not None) else None
    breakeven10 = round(y10 - real10, 2) if (y10 is not None and real10 is not None) else None
    curve = None
    if spread_2 is not None:
        curve = "inverted" if spread_2 < 0 else ("flat" if spread_2 < 0.20 else "upward")
    return {
        "as_of": nom.get("Date"),
        "y3m": y3m, "y2": y2, "y10": y10, "y30": y30,
        "real10": real10, "breakeven10": breakeven10,
        "spread_10y_2y": spread_2, "spread_10y_3m": spread_3m, "curve": curve,
    }


# ── CFTC positioning with 3-year percentile (crowding) ───────────────────────────
# (label, url, market LIKE, long_field, short_field, who, note)
_MARKETS = [
    ("S&P 500", _TFF, "E-MINI S&P 500 -%", "lev_money_positions_long", "lev_money_positions_short", "lev funds", "broad equity risk appetite"),
    ("Nasdaq 100", _TFF, "NASDAQ MINI%", "lev_money_positions_long", "lev_money_positions_short", "lev funds", "growth/tech risk appetite"),
    ("Russell 2000", _TFF, "RUSSELL E-MINI%", "lev_money_positions_long", "lev_money_positions_short", "lev funds", "small-cap / risk-on breadth"),
    ("VIX", _TFF, "VIX FUTURES%", "lev_money_positions_long", "lev_money_positions_short", "lev funds", "net short = complacency, net long = fear/hedging"),
    ("UST 10Y", _TFF, "ULTRA UST 10Y%", "lev_money_positions_long", "lev_money_positions_short", "lev funds", "duration / rate-cut bets"),
    ("Bitcoin", _TFF, "BITCOIN - CHICAGO MERCANTILE%", "lev_money_positions_long", "lev_money_positions_short", "lev funds", "speculative risk appetite"),
    ("Gold", _LEGACY, "GOLD - COMMODITY EXCHANGE%", "noncomm_positions_long_all", "noncomm_positions_short_all", "non-comm", "safe-haven demand"),
    ("Crude oil", _LEGACY, "CRUDE OIL, LIGHT SWEET-WTI%", "noncomm_positions_long_all", "noncomm_positions_short_all", "non-comm", "growth / inflation"),
]


def _pctile(value: float, series: list[float]) -> int | None:
    if not series:
        return None
    return round(100 * sum(1 for x in series if x <= value) / len(series))


def _positioning() -> list[dict]:
    cutoff = (date.today() - timedelta(days=1100)).isoformat()  # ~3 years of weekly history
    out: list[dict] = []
    for label, url, pat, lf, sf, who, note in _MARKETS:
        try:
            params = {
                "$select": f"report_date_as_yyyy_mm_dd,{lf},{sf}",
                "$where": f"market_and_exchange_names like '{pat}' AND report_date_as_yyyy_mm_dd > '{cutoff}'",
                "$order": "report_date_as_yyyy_mm_dd ASC",
                "$limit": 200,
            }
            r = requests.get(url, params=params, headers=_UA, timeout=_TIMEOUT)
            r.raise_for_status()
            rows = r.json()
            series = []
            for row in rows:
                lng, sht = _f(row.get(lf)), _f(row.get(sf))
                if lng is None or sht is None:
                    continue
                series.append((row.get("report_date_as_yyyy_mm_dd", "")[:10], int(lng - sht)))
            if len(series) < 8:
                continue
            nets = [n for _, n in series]
            as_of, net = series[-1]
            prev = series[-2][1]
            pct = _pctile(net, nets)
            extreme = None
            if pct is not None:
                if pct >= 90:
                    extreme = "crowded long"
                elif pct <= 10:
                    extreme = "crowded short"
            out.append({
                "market": label, "net": net, "wow": net - prev, "pctile": pct,
                "lo": min(nets), "hi": max(nets), "as_of": as_of, "who": who,
                "note": note, "extreme": extreme,
                "stance": "net long" if net >= 0 else "net short",
            })
        except Exception:
            continue
    return out


# ── regime synthesis (descriptive) ───────────────────────────────────────────────
def _regime_read(rates: dict | None, pos: list[dict]) -> list[str]:
    out: list[str] = []
    if rates:
        c, s2, s3 = rates.get("curve"), rates.get("spread_10y_2y"), rates.get("spread_10y_3m")
        if c == "inverted" or (s3 is not None and s3 < 0):
            out.append(f"Yield curve inverted (10y-2y {s2:+}, 10y-3m {s3:+}) — classic late-cycle / recession-watch signal.")
        elif c:
            out.append(f"Yield curve {c} (10y-2y {s2:+}) — no curve recession signal.")
        if rates.get("breakeven10") is not None:
            out.append(f"10y breakeven inflation ~{rates['breakeven10']}% (real 10y {rates.get('real10')}%) — the market's priced inflation/real-rate backdrop.")
    by = {p["market"]: p for p in pos}
    vix = by.get("VIX")
    if vix:
        if vix["net"] < 0:
            out.append(f"Leveraged funds net SHORT VIX ({vix['net']:,}, {vix['pctile']} %ile) — positioning for calm (complacency); crowded shorts can snap back violently.")
        else:
            out.append(f"Leveraged funds net LONG VIX ({vix['net']:,}, {vix['pctile']} %ile) — hedging/fear demand for volatility.")
    spx = by.get("S&P 500")
    if spx and spx.get("pctile") is not None:
        if spx["pctile"] >= 80:
            out.append(f"S&P 500 spec positioning crowded long ({spx['pctile']} %ile, 3y) — bullish consensus / euphoria risk.")
        elif spx["pctile"] <= 20:
            out.append(f"S&P 500 spec positioning washed out ({spx['pctile']} %ile, 3y) — bearish consensus / contrarian setup.")
    extremes = [p for p in pos if p.get("extreme")]
    if extremes:
        out.append("Crowded trades flagged: " + ", ".join(f"{p['market']} ({p['extreme']})" for p in extremes) + " — extremes (≥90th/≤10th %ile) often precede reversals.")
    return out


# ── optional FRED macro band (free key) ──────────────────────────────────────────
_FRED_SERIES = [
    ("fed_funds", "DFF", "Fed funds", "%"),
    ("vix", "VIXCLS", "VIX level", ""),
    ("hy_spread", "BAMLH0A0HYM2", "HY credit spread", "%"),
    ("spx", "SP500", "S&P 500", ""),
    ("nasdaq", "NASDAQCOM", "Nasdaq Comp", ""),
    ("dollar", "DTWEXBGS", "US dollar (broad)", ""),
    ("nfci", "NFCI", "Financial conditions (NFCI)", ""),
    ("unrate", "UNRATE", "Unemployment", "%"),
]


def _fred() -> dict | None:
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
    rates = _rates()
    positioning = _positioning()
    macro = _fred()
    sources = [
        "US Treasury — Daily Par Yield Curve, nominal + real/TIPS (home.treasury.gov)",
        "CFTC Commitments of Traders — Traders in Financial Futures + legacy (publicreporting.cftc.gov)",
    ]
    if macro:
        sources.append("FRED — Federal Reserve Bank of St. Louis (fred.stlouisfed.org)")
    return {
        "as_of": (rates or {}).get("as_of") or str(date.today()),
        "rates": rates,
        "positioning": positioning,
        "regime": _regime_read(rates, positioning),
        "macro": macro,
        "macro_available": macro is not None,
        "sources": sources,
        "out_of_reach": (
            "Real-time quotes, options-implied vol, sell-side consensus / price targets, and "
            "proprietary retail-/social-sentiment scores are licensed — not shown."
        ),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_market_context(), indent=2, ensure_ascii=False))
