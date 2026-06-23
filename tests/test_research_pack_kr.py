"""Korean research-pack assembly — pure, offline. Trend (margins, YoY) + renderer."""

from engine.dart import DartProfile, Disclosure, KrPeriod
from engine.research_pack_kr import KrResearchPack, build_trend_kr, render_markdown_kr

PERIODS = [
    KrPeriod(label="제 54 기", revenue=100.0, gross_profit=40.0, operating_income=20.0, net_income=15.0),
    KrPeriod(label="제 55 기", revenue=120.0, gross_profit=54.0, operating_income=30.0, net_income=24.0),
    KrPeriod(label="제 56 기", revenue=150.0, gross_profit=75.0, operating_income=45.0, net_income=30.0),
]


def test_build_trend_kr_margins_and_yoy():
    rows = build_trend_kr(PERIODS)
    assert len(rows) == 3
    assert rows[0].revenue_yoy_pct is None          # no prior year for the first period
    assert rows[1].revenue_yoy_pct == 20.0          # 120 vs 100
    assert rows[1].gross_margin == 45.0             # 54 / 120
    assert rows[2].operating_margin == 30.0         # 45 / 150
    assert rows[2].net_margin == 20.0               # 30 / 150


def test_render_markdown_kr_sections_and_disclaimer():
    pack = KrResearchPack(
        query="삼성전자",
        profile=DartProfile(corp_code="00126380", corp_name="삼성전자",
                            corp_name_eng="SAMSUNG ELECTRONICS", stock_code="005930", industry_code="264"),
        trend=build_trend_kr(PERIODS),
        disclosures=[Disclosure("사업보고서 (2025.12)", "20260311000456", "20260311", "삼성전자",
                                "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260311000456")],
        sources=["Open DART"],
    )
    md = render_markdown_kr(pack)
    assert "# 삼성전자 (005930)" in md
    assert "재무 추이" in md
    assert "제 56 기" in md
    assert "20260311000456" in md                   # disclosure provenance link
    assert "투자자문이 아닙니다" in md                 # §10 disclaimer (Korean)
