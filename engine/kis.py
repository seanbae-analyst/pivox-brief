"""Korean foreign-investor flow via the KIS (한국투자증권) OpenAPI — the one LEGITIMATE source.

KRX's foreign-flow is proprietary and the portal ToS forbids scraping (so pykrx is out). KIS,
by contrast, is an official sanctioned API used with the user's own authenticated keys, read-only
— the clean way to get 외국인 순매수. We poll the per-symbol investor breakdown (TR FHKST01010900,
/quotations/inquire-investor) for a KOSPI large-cap basket and aggregate the recent foreign net
buy. The 모의(paper) domain serves finalized daily investor data, so it works on paper keys too.

Token is cached to data/.kis_token.json (KIS caps issuance to 1/min, tokens last ~24h). Every
call degrades gracefully — no keys, rate limit, or outage just yields None and the brief drops
the factor.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

_TOK = Path(__file__).resolve().parent.parent / "data" / ".kis_token.json"
_TIMEOUT = 12

# KOSPI bellwethers — foreign flow here is the market's strongest KR sentiment tell
_BASKET = [
    ("삼성전자", "005930"), ("SK하이닉스", "000660"), ("현대차", "005380"),
    ("기아", "000270"), ("네이버", "035420"), ("카카오", "035720"),
    ("LG에너지솔루션", "373220"), ("삼성바이오로직스", "207940"),
    ("셀트리온", "068270"), ("POSCO홀딩스", "005490"),
]


def _base() -> str:
    real = os.environ.get("KIS_USE_REAL", "").strip() in ("1", "true", "True")
    return "https://openapi.koreainvestment.com:9443" if real else "https://openapivts.koreainvestment.com:29443"


def _token(key: str, sec: str) -> str | None:
    try:
        c = json.loads(_TOK.read_text(encoding="utf-8"))
        if c.get("token") and c.get("exp", 0) > time.time() + 600:
            return c["token"]
    except Exception:
        pass
    try:
        r = requests.post(_base() + "/oauth2/tokenP",
                          json={"grant_type": "client_credentials", "appkey": key, "appsecret": sec},
                          timeout=_TIMEOUT)
        tok = r.json().get("access_token")
        if not tok:
            return None
        try:
            _TOK.parent.mkdir(parents=True, exist_ok=True)
            _TOK.write_text(json.dumps({"token": tok, "exp": time.time() + 23 * 3600}), encoding="utf-8")
        except Exception:
            pass
        return tok
    except Exception:
        return None


def _investor(base: str, tok: str, key: str, sec: str, code: str) -> list[dict]:
    h = {"authorization": f"Bearer {tok}", "appkey": key, "appsecret": sec,
         "tr_id": "FHKST01010900", "custtype": "P"}
    try:
        r = requests.get(base + "/uapi/domestic-stock/v1/quotations/inquire-investor",
                         headers=h, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
                         timeout=_TIMEOUT)
        return r.json().get("output", []) or []
    except Exception:
        return []


def _f(v) -> float | None:
    try:
        s = str(v).strip()
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


def foreign_flow_kr(days: int = 5) -> dict | None:
    """Aggregate foreign net-buy (거래대금, KRW) over the last `days` finalized sessions across the
    basket. Returns breadth (% of names net-bought) + total KRW + the per-name detail, or None."""
    key, sec = os.environ.get("KIS_APP_KEY", "").strip(), os.environ.get("KIS_APP_SECRET", "").strip()
    if not (key and sec):
        return None
    tok = _token(key, sec)
    if not tok:
        return None
    base = _base()
    bought = total = n = 0
    retail_total = 0          # 개인(리테일) 순매수 합계 — same call, the prsn_* field
    detail = []
    for name, code in _BASKET:
        rows = _investor(base, tok, key, sec, code)
        # rows are newest-first daily; keep finalized (non-empty foreign value) ones
        fin = [r for r in rows if _f(r.get("frgn_ntby_tr_pbmn")) is not None][:days]
        if not fin:
            continue
        net = sum(_f(r.get("frgn_ntby_tr_pbmn")) for r in fin)   # 외국인 순매수 (백만원)
        ret = sum(_f(r.get("prsn_ntby_tr_pbmn")) or 0 for r in fin)  # 개인 순매수 (백만원)
        n += 1
        total += net
        retail_total += ret
        if net > 0:
            bought += 1
        detail.append({"name": name, "net_krw_mn": round(net)})
        time.sleep(0.35)              # KIS 모의 throttles ~2-5/s — stay under it
    if n < 4:
        return None
    breadth = 100 * bought / n
    # magnitude: total foreign net (백만원) over the window mapped to 0-100 (±5조 band)
    t = max(0.0, min(1.0, (total - (-5_000_000)) / (5_000_000 - (-5_000_000))))
    magnitude = t * 100
    score = round(0.5 * breadth + 0.5 * magnitude)  # blend breadth + size → honest sentiment
    return {
        "score": score,               # 0 = 외국인 대량 순매도(공포) … 100 = 대량 순매수(탐욕)
        "breadth": round(breadth), "buy_count": bought, "n": n,
        "total_krw_mn": round(total),
        "total_tril": round(total / 1_000_000, 1),     # 조원
        "retail_tril": round(retail_total / 1_000_000, 1),  # 개인 순매수 (조원)
        "divergence": (total < 0 and retail_total > 0),     # 외국인 매도 ↔ 개인 매수 (개미가 받침)
        "days": days,
        "detail": sorted(detail, key=lambda d: d["net_krw_mn"]),
    }
