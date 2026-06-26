"""Offline tests for the research-scaffold synthesis (engine/scaffold.py).

Pure synthesis over a structured record — no network. Locks that it turns the pack's signals
into a prioritized agenda of area + signal + an OPEN QUESTION (never a verdict), and that it
degrades to None when there's nothing to synthesize.
"""

from __future__ import annotations

from engine.scaffold import build_scaffold

RECORD = {
    "qualitative": {"themes": [
        {"theme": "demand_strength", "direction": "positive", "evidence": "Data Center rev +92%", "source_url": "http://q"},
        {"theme": "margin_pressure", "direction": "negative", "evidence": "component costs rising", "source_url": "http://q"},
    ]},
    "quality_flags": [{"key": "accrual_gap", "observation": "NI exceeded OCF by 14%", "value": 14}],
    "risk_delta": {"added": ["Counterparty exposure from commercial arrangements"], "current_filing": {"url": "http://k"}},
    "ownership": {"insider_pattern": {"open_market_buys": 0, "open_market_sells": 5, "buy_value": 0,
                                      "sell_value": 5e8, "cluster_buy": False, "observation": "5 sales ~$500M"}},
    "peers": {"factors": [{"label": "Operating margin", "value": 60.9, "rank": 1, "n": 6}]},
}


def test_scaffold_synthesizes_each_area():
    s = build_scaffold(RECORD)
    areas = {i["area"] for i in s["items"]}
    assert {"Demand / narrative", "Earnings quality", "New risk (10-K YoY)", "Insider behavior", "Peer position"} <= areas


def test_every_item_is_a_question_not_a_verdict():
    s = build_scaffold(RECORD)
    assert all("?" in i["question"] for i in s["items"])
    ins = next(i for i in s["items"] if i["area"] == "Insider behavior")
    assert "distribution" in ins["question"].lower()   # net-selling → distribution-vs-routine prompt


def test_scaffold_none_when_empty():
    assert build_scaffold({}) is None
    assert build_scaffold({"qualitative": {"themes": []}}) is None


def test_scaffold_caps_themes_and_total():
    themes = [{"theme": "demand_strength", "direction": "positive", "evidence": "x", "source_url": "u"} for _ in range(20)]
    # themes alone are capped at 3 (to leave room for other signal areas)
    assert len(build_scaffold({"qualitative": {"themes": themes}})["items"]) == 3
    # mixed signals beyond the limit → overall max_items cap holds
    rec = {"qualitative": {"themes": themes},
           "quality_flags": [{"key": "accrual_gap", "observation": "o"},
                             {"key": "cash_conversion", "observation": "o"}]}
    assert len(build_scaffold(rec, max_items=4)["items"]) == 4   # 3 themes + 1 quality, capped
