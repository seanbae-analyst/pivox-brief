"""Offline tests for Form 4 parsing + raw-XML URL derivation (engine/ownership.py).

No network: a synthetic Form 4 ownership XML exercises owner/relationship extraction,
transaction parsing, the discretionary (open-market P/S) flag, and value = shares × price.
"""

from __future__ import annotations

from engine import ownership
from engine.edgar import Filing

SAMPLE_FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector><isOfficer>1</isOfficer><officerTitle>Chief Financial Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-06-01</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>50.0</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-06-02</value></transactionDate>
      <transactionCoding><transactionCode>F</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>200</value></transactionShares>
        <transactionPricePerShare><value>51.0</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_parse_form4_extracts_owner_and_transactions():
    txs = ownership.parse_form4(SAMPLE_FORM4, url="http://x")
    assert len(txs) == 2
    assert txs[0]["owner"] == "Doe Jane"
    assert "Chief Financial Officer" in txs[0]["relationship"]


def test_parse_form4_flags_open_market_and_computes_value():
    txs = ownership.parse_form4(SAMPLE_FORM4)
    p, f = txs[0], txs[1]
    assert p["code"] == "P" and p["discretionary"] is True
    assert p["code_label"] == "Open-market purchase"
    assert p["value"] == 50000.0          # 1000 * 50
    assert f["code"] == "F" and f["discretionary"] is False
    assert f["value"] == 10200.0          # 200 * 51


def test_form4_raw_xml_url_strips_xsl_subdir():
    f = Filing(form="4", filing_date="2026-06-23", report_date="2026-06-23", accession="0001696841-26-000008",
               primary_document="xslF345X06/wk-form4_123.xml",
               url="https://www.sec.gov/Archives/edgar/data/1045810/000169684126000008/xslF345X06/wk-form4_123.xml")
    assert ownership.form4_raw_xml_url(f) == (
        "https://www.sec.gov/Archives/edgar/data/1045810/000169684126000008/wk-form4_123.xml"
    )
