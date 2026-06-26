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
# (label, url, EXACT market name, spec_long, spec_short, who, note, inst_long, inst_short)
# spec = the tactical crowd (TFF leveraged-money / legacy non-commercial); inst = TFF asset
# managers (real-money institutions) where available → enables a fast-money-vs-institutions read.
# Names are pinned EXACTLY (not LIKE) — a `like 'PREFIX%'` pattern silently matched multiple
# contracts (e.g. 'EURO FX%' caught EURO FX + EURO FX/JPY + EURO FX/GBP), which interleaved
# different series and, under ASC+limit truncation, surfaced 16-month-old rows as "current".
_AML, _AMS = "asset_mgr_positions_long", "asset_mgr_positions_short"
_LL, _LS = "lev_money_positions_long", "lev_money_positions_short"
_NL, _NS = "noncomm_positions_long_all", "noncomm_positions_short_all"
_MARKETS = [
    ("S&P 500", _TFF, "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE", _LL, _LS, "lev funds", "broad equity risk appetite", _AML, _AMS),
    ("Nasdaq 100", _TFF, "NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE", _LL, _LS, "lev funds", "growth/tech risk appetite", _AML, _AMS),
    ("Russell 2000", _TFF, "RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE", _LL, _LS, "lev funds", "small-cap / risk-on breadth", _AML, _AMS),
    ("VIX", _TFF, "VIX FUTURES - CBOE FUTURES EXCHANGE", _LL, _LS, "lev funds", "net short = complacency, net long = fear/hedging", _AML, _AMS),
    ("UST 10Y", _TFF, "ULTRA UST 10Y - CHICAGO BOARD OF TRADE", _LL, _LS, "lev funds", "duration / rate-cut bets", _AML, _AMS),
    ("Japanese yen", _TFF, "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE", _LL, _LS, "lev funds", "risk-off / carry unwind", _AML, _AMS),
    ("Euro FX", _TFF, "EURO FX - CHICAGO MERCANTILE EXCHANGE", _LL, _LS, "lev funds", "USD alternative", _AML, _AMS),
    ("Bitcoin", _TFF, "BITCOIN - CHICAGO MERCANTILE EXCHANGE", _LL, _LS, "lev funds", "speculative risk appetite", _AML, _AMS),
    ("Gold", _LEGACY, "GOLD - COMMODITY EXCHANGE INC.", _NL, _NS, "non-comm", "safe-haven demand", None, None),
    ("Silver", _LEGACY, "SILVER - COMMODITY EXCHANGE INC.", _NL, _NS, "non-comm", "precious / industrial", None, None),
    ("Copper", _LEGACY, "COPPER- #1 - COMMODITY EXCHANGE INC.", _NL, _NS, "non-comm", "global growth (Dr. Copper)", None, None),
    ("Crude oil", _LEGACY, "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE", _NL, _NS, "non-comm", "growth / inflation", None, None),
]

# Index / rate futures whose leveraged-fund net is dominated by cash-futures BASIS TRADES
# (long cash bond/ETF vs short future) rather than directional sentiment — so a washed-out
# (low) percentile is NOT "bearish consensus". The single most common misread of S&P CoT.
_BASIS_DISTORTED = {"S&P 500", "Nasdaq 100", "Russell 2000", "UST 10Y"}
_BASIS_CAVEAT = (
    "index/rate lev-fund net is dominated by cash-futures basis trades (long cash vs short "
    "future), so a low percentile is a financing/arbitrage footprint, not directional bearishness"
)
_STALE_DAYS = 21  # weekly data is ≤10d fresh; older ⇒ a discontinued contract resolved wrongly


def _pctile(value: float, series: list[float]) -> int | None:
    if not series:
        return None
    return round(100 * sum(1 for x in series if x <= value) / len(series))


def _positioning() -> list[dict]:
    cutoff = (date.today() - timedelta(days=1100)).isoformat()  # ~3 years of weekly history
    today = date.today()
    out: list[dict] = []
    for label, url, name, lf, sf, who, note, ilf, isf in _MARKETS:
        try:
            sel = f"report_date_as_yyyy_mm_dd,{lf},{sf}" + (f",{ilf},{isf}" if ilf else "")
            params = {
                "$select": sel,
                # exact name (no LIKE) ⇒ one contract only; DESC ⇒ always the NEWEST rows
                "$where": f"market_and_exchange_names = '{name}' AND report_date_as_yyyy_mm_dd > '{cutoff}'",
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": 200,
            }
            r = requests.get(url, params=params, headers=_UA, timeout=_TIMEOUT)
            r.raise_for_status()
            rows = r.json()  # newest first
            series = []
            for row in rows:
                lng, sht = _f(row.get(lf)), _f(row.get(sf))
                if lng is None or sht is None:
                    continue
                series.append((row.get("report_date_as_yyyy_mm_dd", "")[:10], int(lng - sht)))
            if len(series) < 8:
                continue
            series.reverse()  # ascending for percentile / wow
            nets = [n for _, n in series]
            as_of, net = series[-1]
            prev = series[-2][1]
            # staleness guard — a dead contract that slipped through resolves to old dates; drop it
            days_old = None
            try:
                days_old = (today - date.fromisoformat(as_of)).days
            except ValueError:
                pass
            if days_old is not None and days_old > _STALE_DAYS:
                continue
            pct = _pctile(net, nets)
            extreme = None
            if pct is not None:
                if pct >= 90:
                    extreme = "crowded long"
                elif pct <= 10:
                    extreme = "crowded short"
            inst_net = None
            if ilf and rows:
                il, ish = _f(rows[0].get(ilf)), _f(rows[0].get(isf))  # rows[0] = newest under DESC
                if il is not None and ish is not None:
                    inst_net = int(il - ish)
            out.append({
                "market": label, "net": net, "wow": net - prev, "pctile": pct,
                "lo": min(nets), "hi": max(nets), "as_of": as_of, "days_old": days_old,
                "who": who, "note": note, "extreme": extreme, "inst_net": inst_net,
                "basis": label in _BASIS_DISTORTED,
                "stance": "net long" if net >= 0 else "net short",
            })
        except Exception:
            continue
    return out


# ── regime synthesis (descriptive) ───────────────────────────────────────────────
def _regime_read(rates: dict | None, pos: list[dict], flow: list[dict] | None = None) -> list[str]:
    out: list[str] = []
    # 0) NEAR-REAL-TIME tape first — daily (T+1) FRED series, the freshest read we can build.
    out += _flow_lines(flow)
    if rates:
        c, s2, s3 = rates.get("curve"), rates.get("spread_10y_2y"), rates.get("spread_10y_3m")
        if c == "inverted" or (s3 is not None and s3 < 0):
            out.append(f"Yield curve inverted (10y-2y {s2:+}, 10y-3m {s3:+}) — classic late-cycle / recession-watch signal.")
        elif c:
            out.append(f"Yield curve {c} (10y-2y {s2:+}) — no curve recession signal.")
        if rates.get("breakeven10") is not None:
            out.append(f"10y breakeven inflation ~{rates['breakeven10']}% (real 10y {rates.get('real10')}%) — the market's priced inflation/real-rate backdrop.")
    # CFTC positioning is WEEKLY and lagged — tag every line so it never reads as "now".
    ds = [p["days_old"] for p in pos if p.get("days_old") is not None]
    lag = f" [CFTC weekly, ~{min(ds)}d lagged]" if ds else " [CFTC weekly, lagged]"
    by = {p["market"]: p for p in pos}
    vix = by.get("VIX")
    if vix:
        if vix["net"] < 0:
            out.append(f"Leveraged funds net SHORT VIX ({vix['net']:,}, {vix['pctile']} %ile) — positioning for calm (complacency); crowded shorts can snap back violently.{lag}")
        else:
            out.append(f"Leveraged funds net LONG VIX ({vix['net']:,}, {vix['pctile']} %ile) — hedging/fear demand for volatility.{lag}")
    spx = by.get("S&P 500")
    if spx and spx.get("pctile") is not None:
        # NOTE: S&P lev-fund net is basis-trade driven — do NOT read low %ile as bearish.
        if spx["pctile"] >= 80:
            out.append(f"S&P 500 lev-fund net rich ({spx['pctile']} %ile, 3y) — note {_BASIS_CAVEAT}.{lag}")
        elif spx["pctile"] <= 20:
            out.append(f"S&P 500 lev-fund net washed out ({spx['pctile']} %ile, 3y) — NOT a bearish/contrarian signal: {_BASIS_CAVEAT}.{lag}")
    for mk in ("S&P 500", "VIX", "Nasdaq 100"):
        p = by.get(mk)
        if p and p.get("inst_net") is not None and p.get("net") is not None and (p["net"] >= 0) != (p["inst_net"] >= 0):
            tail = f" (on {mk} the hedge-fund leg is largely basis/financing, not a directional view)" if p.get("basis") else ""
            out.append(
                f"Positioning split on {mk}: hedge funds net {'long' if p['net'] >= 0 else 'short'} "
                f"({p['net']:,}) vs asset managers net {'long' if p['inst_net'] >= 0 else 'short'} "
                f"({p['inst_net']:,}){tail}.{lag}"
            )
    # genuine sentiment extremes (reversal-relevant) vs basis-driven ones (financing, not sentiment)
    extremes = [p for p in pos if p.get("extreme") and not p.get("basis")]
    if extremes:
        out.append("Crowded trades flagged: " + ", ".join(f"{p['market']} ({p['extreme']})" for p in extremes) + f" — extremes (≥90th/≤10th %ile) often precede reversals.{lag}")
    basis_ext = [p for p in pos if p.get("extreme") and p.get("basis")]
    if basis_ext:
        out.append("Excluded from the reversal read (basis/financing, not sentiment): " + ", ".join(f"{p['market']} ({p['extreme']})" for p in basis_ext) + f".{lag}")
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


# Korea macro — the clean slice available free/official (FRED/OECD/BIS). The high-signal KR
# sentiment (foreign-investor flows, KOSPI/VKOSPI) is KRX-proprietary → named as a blind spot.
_KR_SERIES = [
    ("krw", "DEXKOUS", "KRW/USD", ""),
    ("kr_3m", "IR3TIB01KRM156N", "KR 3M rate", "%"),
    ("kr_10y", "IRLTLT01KRM156N", "KR 10Y bond", "%"),
    ("kr_unrate", "LRHUTTTTKRM156S", "KR unemployment", "%"),
]


def _fred_fetch(key: str, series: list[tuple]) -> dict | None:
    out: dict = {}
    for fld, sid, label, unit in series:
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
                out[fld] = {"value": val, "as_of": obs[0]["date"], "label": label, "unit": unit}
        except Exception:
            continue
    return out or None


def _fred() -> dict | None:
    key = os.environ.get("FRED_API_KEY")
    return _fred_fetch(key, _FRED_SERIES) if key else None


# ── near-real-time daily flow (FRED daily series, T+1) ────────────────────────────
# CoT is structurally weekly+lagged; this is the freshest tape free/official data allows.
# We compute not just the level but the 5- and 20-trading-day CHANGE → an actual "what's
# moving now" read (equities, vol, dollar, credit, the long end), updated each business day.
# (label, series_id, kind)  kind: "pct" = % change · "level" = absolute · "bp" = %→basis-points
_FLOW_SERIES = [
    ("S&P 500", "SP500", "pct"),
    ("Nasdaq", "NASDAQCOM", "pct"),
    ("VIX", "VIXCLS", "level"),
    ("US dollar", "DTWEXBGS", "pct"),
    ("HY spread", "BAMLH0A0HYM2", "bp"),
    ("UST 10Y", "DGS10", "bp"),
]


def _fred_history(key: str, sid: str, n: int = 45) -> list[tuple[str, float]]:
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": sid, "api_key": key, "file_type": "json",
                    "sort_order": "desc", "limit": n},
            headers=_UA, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        ser = []
        for o in r.json().get("observations", []):
            v = _f(o.get("value"))
            if v is not None:
                ser.append((o["date"], v))
        ser.reverse()  # ascending
        return ser
    except Exception:
        return []


def _daily_flow() -> list[dict] | None:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None
    out: list[dict] = []
    for label, sid, kind in _FLOW_SERIES:
        ser = _fred_history(key, sid)
        if len(ser) < 6:
            continue
        as_of, last = ser[-1]
        item = {"label": label, "value": last, "as_of": as_of, "kind": kind}

        def back(nb: int) -> float | None:
            return ser[-1 - nb][1] if len(ser) > nb else None

        b5, b20 = back(5), back(20)
        if kind == "pct":
            item["chg5_pct"] = round(100 * (last - b5) / b5, 1) if b5 else None
            item["chg20_pct"] = round(100 * (last - b20) / b20, 1) if b20 else None
        elif kind == "bp":
            item["chg5_bp"] = round(100 * (last - b5)) if b5 is not None else None
            item["chg20_bp"] = round(100 * (last - b20)) if b20 is not None else None
        else:  # level (VIX)
            item["chg5"] = round(last - b5, 2) if b5 is not None else None
            item["chg20"] = round(last - b20, 2) if b20 is not None else None
        out.append(item)
    return out or None


def _flow_lines(flow: list[dict] | None) -> list[str]:
    if not flow:
        return []
    parts: list[str] = []
    for f in flow:
        lbl, k = f["label"], f["kind"]
        if k == "pct" and f.get("chg5_pct") is not None:
            parts.append(f"{lbl} {f['chg5_pct']:+.1f}% 5d")
        elif k == "bp" and f.get("chg5_bp") is not None:
            parts.append(f"{lbl} {f['value']:.2f}% ({f['chg5_bp']:+d}bp 5d)")
        elif k == "level" and f.get("chg5") is not None:
            parts.append(f"{lbl} {f['value']:.1f} ({f['chg5']:+.1f} 5d)")
    if not parts:
        return []
    by = {f["label"]: f for f in flow}
    lines = [f"Near-real-time tape (FRED daily, T+1, as of {flow[0].get('as_of')}): " + "; ".join(parts) + "."]
    # directional classifier from the three cleanest risk axes
    sig, bits = 0, []
    spx, vix, hy = by.get("S&P 500"), by.get("VIX"), by.get("HY spread")
    if spx and spx.get("chg5_pct") is not None:
        up = spx["chg5_pct"] > 0; sig += 1 if up else -1; bits.append("equities " + ("up" if up else "down"))
    if vix and vix.get("chg5") is not None:
        dn = vix["chg5"] < 0; sig += 1 if dn else -1; bits.append("vol " + ("falling" if dn else "rising"))
    if hy and hy.get("chg5_bp") is not None:
        tt = hy["chg5_bp"] < 0; sig += 1 if tt else -1; bits.append("credit " + ("tightening" if tt else "widening"))
    if bits:
        tilt = "risk-on tilt" if sig >= 2 else ("risk-off tilt" if sig <= -2 else "mixed/rotational")
        lines.append(f"5-day tape: {tilt} ({', '.join(bits)}).")
    return lines


def _kr_macro() -> dict | None:
    key = os.environ.get("FRED_API_KEY")
    return _fred_fetch(key, _KR_SERIES) if key else None


def build_market_context() -> dict:
    rates = _rates()
    positioning = _positioning()
    flow = _daily_flow()
    macro = _fred()
    kr_macro = _kr_macro()
    sources = [
        "US Treasury — Daily Par Yield Curve, nominal + real/TIPS (home.treasury.gov)",
        "CFTC Commitments of Traders — Traders in Financial Futures + legacy (publicreporting.cftc.gov)",
    ]
    if macro or flow:
        sources.append("FRED — Federal Reserve Bank of St. Louis (fred.stlouisfed.org)")
    pos_ds = [p["days_old"] for p in positioning if p.get("days_old") is not None]
    return {
        # primary as_of = the freshest layer we have (daily flow > daily rates > weekly CoT)
        "as_of": (flow[0]["as_of"] if flow else None) or (rates or {}).get("as_of") or str(date.today()),
        "rates": rates,
        "daily_flow": flow,
        "flow_available": flow is not None,
        "flow_as_of": flow[0]["as_of"] if flow else None,
        "positioning": positioning,
        "positioning_as_of": max((p["as_of"] for p in positioning), default=None),
        "positioning_lag_days": min(pos_ds) if pos_ds else None,
        "regime": _regime_read(rates, positioning, flow),
        "macro": macro,
        "macro_available": macro is not None,
        "kr_macro": kr_macro,
        "sources": sources,
        "out_of_reach": (
            "Real-time quotes, options-implied vol, sell-side consensus / price targets, and "
            "proprietary retail-/social-sentiment scores are licensed — not shown."
        ),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_market_context(), indent=2, ensure_ascii=False))
