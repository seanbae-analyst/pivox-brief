"""Open DART parsers — pure, offline. Fixtures follow DART's documented response
shapes (corpCode.xml ZIP, company/list/fnlttSinglAcntAll JSON). No network, no key.

Live end-to-end is pending the user's DART_API_KEY; these lock the parsing logic
so that once the key is set, only the HTTP layer needs a confirming smoke run."""

import io
import zipfile

from engine.dart import (
    _num,
    annual_financials,  # noqa: F401  (import smoke; exercised live, not here)
    match_corp,
    parse_company,
    parse_corp_codes,
    parse_disclosures,
    parse_financials,
)


def _corp_zip() -> bytes:
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n<result>\n'
        '<list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name>'
        '<stock_code>005930</stock_code><modify_date>20260101</modify_date></list>\n'
        '<list><corp_code>00164779</corp_code><corp_name>SK하이닉스</corp_name>'
        '<stock_code>000660</stock_code><modify_date>20260101</modify_date></list>\n'
        '<list><corp_code>00999999</corp_code><corp_name>비상장기업</corp_name>'
        '<stock_code> </stock_code><modify_date>20260101</modify_date></list>\n'
        '</result>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("CORPCODE.xml", xml.encode("utf-8"))
    return buf.getvalue()


COMPANY = {
    "status": "000", "message": "정상",
    "corp_code": "00126380", "corp_name": "삼성전자", "corp_name_eng": "SAMSUNG ELECTRONICS CO,.LTD",
    "stock_code": "005930", "induty_code": "264",
}

DISCLOSURES = {
    "status": "000", "message": "정상",
    "list": [
        {"corp_name": "삼성전자", "stock_code": "005930", "report_nm": "분기보고서 (2026.03)",
         "rcept_no": "20260515000123", "flr_nm": "삼성전자", "rcept_dt": "20260515"},
        {"corp_name": "삼성전자", "stock_code": "005930", "report_nm": "사업보고서 (2025.12)",
         "rcept_no": "20260311000456", "flr_nm": "삼성전자", "rcept_dt": "20260311"},
    ],
}

FINANCIALS = {
    "status": "000", "message": "정상",
    "list": [
        {"sj_div": "IS", "account_id": "ifrs-full_Revenue", "account_nm": "매출액",
         "thstrm_nm": "제 56 기", "thstrm_amount": "300,870,903",
         "frmtrm_nm": "제 55 기", "frmtrm_amount": "258,935,494",
         "bfefrmtrm_nm": "제 54 기", "bfefrmtrm_amount": "302,231,360"},
        {"sj_div": "IS", "account_id": "ifrs-full_GrossProfit", "account_nm": "매출총이익",
         "thstrm_amount": "120,000,000", "frmtrm_amount": "100,000,000", "bfefrmtrm_amount": "110,000,000"},
        {"sj_div": "IS", "account_id": "dart_OperatingIncomeLoss", "account_nm": "영업이익",
         "thstrm_amount": "32,725,961", "frmtrm_amount": "6,566,976", "bfefrmtrm_amount": "43,376,630"},
        {"sj_div": "IS", "account_id": "ifrs-full_ProfitLoss", "account_nm": "당기순이익",
         "thstrm_amount": "34,451,351", "frmtrm_amount": "(5,000,000)", "bfefrmtrm_amount": "55,654,077"},
        {"sj_div": "BS", "account_id": "ifrs-full_Assets", "account_nm": "자산총계",
         "thstrm_amount": "999"},   # balance-sheet row must be ignored
    ],
}


def test_num_parses_korean_amounts():
    assert _num("300,870,903") == 300870903.0
    assert _num("(5,000,000)") == -5000000.0   # parentheses = negative
    assert _num("-") is None and _num("") is None


def test_parse_corp_codes_and_match():
    corps = parse_corp_codes(_corp_zip())
    assert len(corps) == 3
    assert match_corp(corps, "005930").corp_name == "삼성전자"       # 6-digit ticker
    assert match_corp(corps, "삼성전자").stock_code == "005930"       # exact name
    assert match_corp(corps, "하이닉스").corp_name == "SK하이닉스"     # substring
    assert match_corp(corps, "비상장기업") is None                    # unlisted excluded


def test_parse_company():
    p = parse_company(COMPANY)
    assert p.corp_name == "삼성전자" and p.stock_code == "005930"
    assert parse_company({"status": "013", "message": "no data"}) is None


def test_parse_disclosures():
    ds = parse_disclosures(DISCLOSURES, limit=10)
    assert len(ds) == 2
    assert ds[0].report_nm.startswith("분기보고서")
    assert ds[0].url == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260515000123"


def test_parse_financials_three_periods_oldest_first():
    periods = parse_financials(FINANCIALS)
    assert len(periods) == 3
    # DART lists newest term first; we reverse to oldest -> newest for a trend
    assert periods[0].label == "제 54 기" and periods[0].revenue == 302231360.0
    assert periods[-1].label == "제 56 기" and periods[-1].revenue == 300870903.0
    assert periods[-1].operating_income == 32725961.0
    assert periods[1].net_income == -5000000.0          # parenthesized negative
    assert periods[0].gross_profit == 110000000.0       # balance-sheet row ignored


def test_parse_financials_error_status():
    assert parse_financials({"status": "013", "message": "no data"}) is None
