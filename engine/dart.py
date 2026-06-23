"""Open DART client — Korean issuer data (RESEARCH_PACK_PLAN.md step 2).

FSS official Korean disclosure API (https://opendart.fss.or.kr). Unlike SEC EDGAR
it requires a free API key — register and set ``DART_API_KEY`` in .env. Endpoints:

  name / stock_code -> corp_code   /api/corpCode.xml          (ZIP of CORPCODE.xml)
  company profile                  /api/company.json
  recent disclosures               /api/list.json
  financial statements             /api/fnlttSinglAcntAll.json (reprt_code, fs_div)

Cleanest KR source (DATA_SOURCES.md): the official regulator feed — no scraping,
derived facts + provenance links only. I/O (``_get*``) is split from pure parsers
(``parse_*`` / ``match_corp``) so the parsers unit-test offline.

STATUS: parsers are offline-tested against DART's documented response shapes;
income-statement accounts are matched by BOTH Korean name and ``account_id`` for
robustness. Live end-to-end is pending the user's DART_API_KEY — one smoke run
through scripts/research.py (KR routing) then confirms or corrects the live shapes.
"""

from __future__ import annotations

import io
import os
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import requests

DART_BASE = "https://opendart.fss.or.kr/api"
DISCLOSURE_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="

# Periodic-report codes (reprt_code).
REPORT_CODES = {"Q1": "11013", "H1": "11012", "Q3": "11014", "ANNUAL": "11011"}

# Income-statement accounts we extract — matched by Korean name (stable in DART's
# IS) first, with account_id as a secondary signal. KR operating income uses DART's
# own extension tag (dart_OperatingIncomeLoss), not an ifrs-full tag.
_REVENUE_NAMES = {"매출액", "수익(매출액)", "영업수익", "매출"}
_GROSS_NAMES = {"매출총이익"}
_OPINC_NAMES = {"영업이익", "영업이익(손실)"}
_NETINC_NAMES = {"당기순이익", "당기순이익(손실)", "당기순이익(당기손실)"}
_REVENUE_IDS = {"ifrs-full_Revenue", "ifrs_Revenue"}
_GROSS_IDS = {"ifrs-full_GrossProfit"}
_OPINC_IDS = {"dart_OperatingIncomeLoss", "ifrs-full_OperatingIncome"}
_NETINC_IDS = {"ifrs-full_ProfitLoss", "ifrs-full_ProfitLossAttributableToOwnersOfParent"}


@dataclass
class CorpRef:
    corp_code: str       # 8-digit DART code
    corp_name: str
    stock_code: str      # 6-digit KRX ticker ("" for unlisted entities)


@dataclass
class DartProfile:
    corp_code: str
    corp_name: str
    corp_name_eng: str
    stock_code: str
    industry_code: str


@dataclass
class Disclosure:
    report_nm: str
    rcept_no: str
    rcept_dt: str
    flr_nm: str
    url: str             # DART viewer link (provenance)


@dataclass
class KrPeriod:
    label: str           # term label from DART, e.g. "제 56 기"
    revenue: Optional[float]
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None


# ── pure parsers ─────────────────────────────────────────────────────────────
def parse_corp_codes(zip_bytes: bytes) -> list[CorpRef]:
    """corpCode.xml ZIP -> CorpRef list (includes unlisted entities, stock_code='')."""
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    xml_name = next(n for n in zf.namelist() if n.lower().endswith(".xml"))
    root = ET.fromstring(zf.read(xml_name))
    out: list[CorpRef] = []
    for el in root.iter("list"):
        out.append(CorpRef(
            corp_code=(el.findtext("corp_code") or "").strip(),
            corp_name=(el.findtext("corp_name") or "").strip(),
            stock_code=(el.findtext("stock_code") or "").strip(),
        ))
    return out


def match_corp(corps: list[CorpRef], query: str) -> Optional[CorpRef]:
    """Resolve a 6-digit KRX code (exact) or company name (exact, then substring).
    Only listed companies (a non-empty stock_code) are considered for names."""
    q = query.strip()
    if not q:
        return None
    if q.isdigit() and len(q) == 6:
        return next((c for c in corps if c.stock_code == q), None)
    listed = [c for c in corps if c.stock_code]
    exact = next((c for c in listed if c.corp_name == q), None)
    if exact:
        return exact
    ql = q.lower()
    return next((c for c in listed if ql in c.corp_name.lower()), None)


def parse_company(data: dict) -> Optional[DartProfile]:
    if data.get("status") != "000":
        return None
    return DartProfile(
        corp_code=data.get("corp_code", ""),
        corp_name=data.get("corp_name", ""),
        corp_name_eng=data.get("corp_name_eng", ""),
        stock_code=data.get("stock_code", ""),
        industry_code=data.get("induty_code", ""),
    )


def parse_disclosures(data: dict, limit: int = 10) -> list[Disclosure]:
    if data.get("status") != "000":
        return []
    out: list[Disclosure] = []
    for r in data.get("list", [])[:limit]:
        rno = (r.get("rcept_no") or "").strip()
        out.append(Disclosure(
            report_nm=(r.get("report_nm") or "").strip(),
            rcept_no=rno,
            rcept_dt=(r.get("rcept_dt") or "").strip(),
            flr_nm=(r.get("flr_nm") or "").strip(),
            url=(DISCLOSURE_VIEWER + rno) if rno else "",
        ))
    return out


def _num(s: object) -> Optional[float]:
    """DART amounts are comma-grouped strings; '( )' marks negatives; '-'/'' = none."""
    text = str(s or "").strip().replace(",", "")
    if not text or text in ("-", "–", "—"):
        return None
    neg = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        val = float(text)
    except ValueError:
        return None
    return -val if neg else val


def _matches(item: dict, names: set[str], ids: set[str]) -> bool:
    return item.get("account_id") in ids or (item.get("account_nm") or "").strip() in names


def parse_financials(data: dict) -> Optional[list[KrPeriod]]:
    """fnlttSinglAcntAll.json -> up to 3 periods (this / prior / before-prior term),
    oldest first. Income-statement rows only. None if the call failed or no revenue."""
    if data.get("status") != "000":
        return None
    is_rows = [r for r in data.get("list", []) if r.get("sj_div") in ("IS", "CIS")]

    def pick(names: set[str], ids: set[str]) -> Optional[dict]:
        return next((r for r in is_rows if _matches(r, names, ids)), None)

    rev = pick(_REVENUE_NAMES, _REVENUE_IDS)
    if not rev:
        return None
    gp, oi, ni = (pick(n, i) for n, i in (
        (_GROSS_NAMES, _GROSS_IDS), (_OPINC_NAMES, _OPINC_IDS), (_NETINC_NAMES, _NETINC_IDS)))

    periods: list[KrPeriod] = []
    for amt, nm in (("thstrm_amount", "thstrm_nm"), ("frmtrm_amount", "frmtrm_nm"),
                    ("bfefrmtrm_amount", "bfefrmtrm_nm")):
        revenue = _num(rev.get(amt))
        if revenue is None:
            continue
        periods.append(KrPeriod(
            label=(rev.get(nm) or amt).strip(),
            revenue=revenue,
            gross_profit=_num(gp.get(amt)) if gp else None,
            operating_income=_num(oi.get(amt)) if oi else None,
            net_income=_num(ni.get(amt)) if ni else None,
        ))
    return list(reversed(periods))   # DART lists newest term first; trend wants oldest->newest


# ── I/O wrappers (need DART_API_KEY) ─────────────────────────────────────────
def _key() -> str:
    k = os.environ.get("DART_API_KEY")
    if not k:
        raise RuntimeError(
            "DART_API_KEY not set — register free at https://opendart.fss.or.kr and add it to .env"
        )
    return k


def _get_json(path: str, **params) -> dict:
    params["crtfc_key"] = _key()
    resp = requests.get(f"{DART_BASE}/{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get_bytes(path: str, **params) -> bytes:
    params["crtfc_key"] = _key()
    resp = requests.get(f"{DART_BASE}/{path}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.content


_corp_cache: Optional[list[CorpRef]] = None


def resolve_corp(query: str) -> Optional[CorpRef]:
    """Resolve a KRX ticker / company name to a CorpRef (corpCode.xml, cached)."""
    global _corp_cache
    if _corp_cache is None:
        _corp_cache = parse_corp_codes(_get_bytes("corpCode.xml"))
    return match_corp(_corp_cache, query)


def company_profile(corp_code: str) -> Optional[DartProfile]:
    return parse_company(_get_json("company.json", corp_code=corp_code))


def disclosures(corp_code: str, limit: int = 10, bgn_de: Optional[str] = None,
                pblntf_ty: Optional[str] = "A") -> list[Disclosure]:
    """Recent disclosures. DART's list.json REQUIRES a begin date — without bgn_de it
    returns status 013 ("no data") — so default to ~18 months back. ``pblntf_ty='A'``
    keeps only periodic reports (사업/반기/분기보고서), the KR earnings-read equivalent;
    pass ``pblntf_ty=None`` for all disclosure types."""
    if bgn_de is None:
        bgn_de = (date.today() - timedelta(days=550)).strftime("%Y%m%d")
    params = {"corp_code": corp_code, "page_count": str(limit), "bgn_de": bgn_de}
    if pblntf_ty:
        params["pblntf_ty"] = pblntf_ty
    return parse_disclosures(_get_json("list.json", **params), limit=limit)


def annual_financials(corp_code: str, year: int, fs_div: str = "CFS") -> Optional[list[KrPeriod]]:
    """Annual income-statement trend (3 years: this / prior / before-prior term)."""
    data = _get_json("fnlttSinglAcntAll.json", corp_code=corp_code,
                     bsns_year=str(year), reprt_code=REPORT_CODES["ANNUAL"], fs_div=fs_div)
    return parse_financials(data)
