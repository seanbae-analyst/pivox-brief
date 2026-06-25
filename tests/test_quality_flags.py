"""Offline tests for earnings-quality flags (engine/quality_flags.py).

Pure computation over synthetic trend rows + XBRL series. Locks the cash-quality math,
trajectory direction, dilution sign, and graceful omission of absent inputs. Descriptive
only — we assert the numbers and the observation wording, never a verdict.
"""

from __future__ import annotations

from types import SimpleNamespace

from engine.edgar import FactPoint, FinancialSeries
from engine.quality_flags import quality_flags


def series(pairs):
    return FinancialSeries(concept="t", points=[
        FactPoint(end=e, val=v, fy=None, fp=None, form="10-K", frame=None, start=None) for e, v in pairs])


def row(net_margin, yoy):
    return SimpleNamespace(net_margin=net_margin, operating_margin=None, revenue_yoy_pct=yoy)


def test_cash_quality_math():
    ext = {"net_income_annual": series([("2025-12-31", 100.0)]),
           "ocf": series([("2025-12-31", 120.0)]),
           "capex": series([("2025-12-31", 20.0)])}
    f = {x["key"]: x for x in quality_flags([], ext)}
    assert f["accrual_gap"]["value"] == -20.0       # (100-120)/100 → NI trailed OCF by 20%
    assert "trailed" in f["accrual_gap"]["observation"]
    assert f["cash_conversion"]["value"] == 1.2     # 120/100
    assert f["fcf_conversion"]["value"] == 1.0      # (120-20)/100


def test_trajectory_direction():
    trend = [row(40, 50), row(45, 40), row(50, 30)]  # margin rising, growth decelerating
    f = {x["key"]: x for x in quality_flags(trend, {})}
    assert f["net_margin_trend"]["value"] == "rising"
    assert f["rev_growth_trend"]["value"] == "falling"
    assert "→" in f["net_margin_trend"]["observation"]


def test_dilution_sign():
    ext = {"shares": series([("2025-03-31", 110.0), ("2026-03-31", 100.0)])}
    f = {x["key"]: x for x in quality_flags([], ext)}
    assert f["share_count_change"]["value"] == -9.1
    assert "net buyback" in f["share_count_change"]["observation"]


def test_net_loss_emits_neutral_observation_not_ratios():
    ext = {"net_income_annual": series([("2025-12-31", -50.0)]),
           "ocf": series([("2025-12-31", 30.0)]),
           "capex": series([("2025-12-31", 10.0)])}
    f = {x["key"]: x for x in quality_flags([], ext)}
    assert "net_loss" in f                  # neutral loss flag emitted
    assert "cash_conversion" not in f       # ratios omitted (would be -0.6x — nonsense)
    assert "fcf_conversion" not in f
    assert "not meaningful" in f["net_loss"]["observation"]


def test_omits_absent_inputs():
    assert quality_flags([], {}) == []
