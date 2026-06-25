"""Korean research pack (RESEARCH_PACK_PLAN.md — KR side of step 4).

Assembles a Korean-language one-page brief for a KRX issuer from Open DART
(engine.dart) and renders it in Korean. Kept separate from engine.research_pack
(US/EDGAR) because the KR financial shape (annual KrPeriod) and the output language
differ. The pure parts — trend derivation and the renderer — unit-test offline;
``build_kr_pack`` is the I/O entry point and needs DART_API_KEY (engine.dart).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Optional

from engine import dart
from engine.dart import DartProfile, Disclosure, KrPeriod


@dataclass
class KrTrendRow:
    label: str
    revenue: Optional[float]
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    revenue_yoy_pct: Optional[float] = None


@dataclass
class KrResearchPack:
    query: str
    profile: DartProfile
    trend: list[KrTrendRow] = field(default_factory=list)
    disclosures: list[Disclosure] = field(default_factory=list)
    news: list = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def to_kr_page_dict(pack: "KrResearchPack") -> dict:
    """Serialise a KR pack into the page render dict (language='ko'). Shared by the
    static builder (scripts/build_pack_page.py) and the live search API (api/research.py)."""
    def _d(obj):
        return asdict(obj) if is_dataclass(obj) else obj
    p = pack.profile
    return {
        "language": "ko",
        "ticker": p.stock_code or pack.query,
        "name": p.corp_name,
        "name_eng": p.corp_name_eng,
        "exchanges": ["KRX"],
        "cik": p.corp_code,                      # DART 고유번호 (rendered as "DART …")
        "price": None,
        "trend": [{"period": r.label, "revenue": r.revenue, "gross_margin": r.gross_margin,
                   "operating_margin": r.operating_margin, "net_margin": r.net_margin,
                   "revenue_yoy_pct": r.revenue_yoy_pct} for r in pack.trend],
        "disclosures": [_d(d) for d in pack.disclosures],
        "news": [_d(n) for n in pack.news],
        "sources": pack.sources,
    }


# ── pure assembly ────────────────────────────────────────────────────────────
def _margin(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
    if numer is None or not denom:
        return None
    return round(numer / denom * 100.0, 1)


def build_trend_kr(periods: list[KrPeriod]) -> list[KrTrendRow]:
    """Annual margins + revenue YoY from DART periods (already oldest -> newest)."""
    rows: list[KrTrendRow] = []
    prev_rev: Optional[float] = None
    for p in periods:
        yoy = (round((p.revenue / prev_rev - 1.0) * 100.0, 1)
               if (prev_rev and p.revenue is not None) else None)
        rows.append(KrTrendRow(
            label=p.label,
            revenue=p.revenue,
            gross_margin=_margin(p.gross_profit, p.revenue),
            operating_margin=_margin(p.operating_income, p.revenue),
            net_margin=_margin(p.net_income, p.revenue),
            revenue_yoy_pct=yoy,
        ))
        prev_rev = p.revenue
    return rows


# ── I/O entry point (needs DART_API_KEY) ─────────────────────────────────────
def build_kr_pack(query: str, year: int) -> Optional[KrResearchPack]:
    """Resolve a KRX ticker/name via DART and assemble its Korean research pack.
    None if the query doesn't resolve in DART. Raises if DART_API_KEY is unset."""
    ref = dart.resolve_corp(query)
    if ref is None:
        return None

    from concurrent.futures import ThreadPoolExecutor

    from engine.news import load_news

    def _safe(fn, *a, **k):
        try:
            return fn(*a, **k)
        except Exception:
            return None

    # corp_code is resolved; the four reads below are independent → fetch them in parallel
    # (DART calls dominate KR latency). Each is guarded so one flaky read can't 500 the pack.
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_profile = ex.submit(_safe, dart.company_profile, ref.corp_code)
        f_disc = ex.submit(_safe, dart.disclosures, ref.corp_code, limit=8)
        f_fin = ex.submit(_safe, dart.annual_financials, ref.corp_code, year)
        f_news = ex.submit(_safe, load_news, ref.stock_code or ref.corp_name)

    profile = f_profile.result() or DartProfile(
        corp_code=ref.corp_code, corp_name=ref.corp_name, corp_name_eng="",
        stock_code=ref.stock_code, industry_code="")
    sources = [
        f"Open DART 공시뷰어 — https://dart.fss.or.kr (기업: {ref.corp_name}, 종목 {ref.stock_code})",
        "Open DART 정기보고서 재무정보 (fnlttSinglAcntAll)",
    ]
    return KrResearchPack(
        query=query,
        profile=profile,
        trend=build_trend_kr(f_fin.result() or []),
        disclosures=f_disc.result() or [],
        news=f_news.result() or [],
        sources=sources,
    )


# ── rendering (Korean) ───────────────────────────────────────────────────────
def _fmt_won(v: Optional[float]) -> str:
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e12:
        return f"{v / 1e12:.1f}조원"
    if a >= 1e8:
        return f"{v / 1e8:.0f}억원"
    return f"{v:,.0f}원"


def _pct(v: Optional[float], sign: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v:+.1f}%" if sign else f"{v:.1f}%"


def render_markdown_kr(pack: KrResearchPack) -> str:
    """한 페이지 한국어 리서치 브리프."""
    p = pack.profile
    ticker = p.stock_code or pack.query
    lines: list[str] = []

    lines.append(f"# {p.corp_name} ({ticker})")
    snap = ["**시장:** KRX", f"**종목코드:** {p.stock_code or '—'}", f"**DART 고유번호:** {p.corp_code}"]
    if p.corp_name_eng:
        snap.append(f"**영문명:** {p.corp_name_eng}")
    lines.append("  •  ".join(snap))
    lines.append("")

    lines.append("## 재무 추이 (연간, DART 정기보고서)")
    if pack.trend:
        lines.append("| 기수 | 매출액 | 매출 성장(YoY) | 매출총이익률 | 영업이익률 | 순이익률 |")
        lines.append("|---|--:|--:|--:|--:|--:|")
        for r in pack.trend:
            lines.append(
                f"| {r.label} | {_fmt_won(r.revenue)} | {_pct(r.revenue_yoy_pct, sign=True)} | "
                f"{_pct(r.gross_margin)} | {_pct(r.operating_margin)} | {_pct(r.net_margin)} |"
            )
    else:
        lines.append("_표준 재무정보를 불러오지 못했습니다 (DART_API_KEY · 사업연도 · fs_div 확인)._")
    lines.append("")

    lines.append("## 공시 (Earnings read)")
    if pack.disclosures:
        for d in pack.disclosures:
            who = f" · {d.flr_nm}" if d.flr_nm else ""
            lines.append(f"- **{d.report_nm}** · 접수 {d.rcept_dt}{who} — [{d.rcept_no}]({d.url})")
    else:
        lines.append("_최근 공시 없음._")
    lines.append("")

    lines.append("## 뉴스 & 촉매")
    if pack.news:
        for n in pack.news:
            meta = " · ".join(x for x in (n.source, n.date) if x)
            lines.append(f"- [{n.headline}]({n.url})" + (f" — {meta}" if meta else ""))
        lines.append("")
        lines.append("_헤드라인 + 링크만 (DATA_SOURCES.md §4); 본문은 복제하지 않습니다._")
    else:
        lines.append("_캐시된 헤드라인 없음 — `data/news/<종목코드>.json` 에 추가 (헤드라인 + 링크만, §4)._")
    lines.append("")

    lines.append("## 출처")
    for s in pack.sources:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("---")
    lines.append("*공개된 DART 공시를 바탕으로 정리한 리서치 출발점 — 서술적 정보일 뿐 "
                 "**투자자문이 아닙니다** (§10). 행동 전 원본 공시를 확인하세요.*")
    return "\n".join(lines)
