"""Morning brief logic — alert triggers + tilt classifier + readability reads. Offline."""

from engine.brief import _kr_read, _tilt, _us_rotation, detect_alerts


def _sec(label, group, chg5):
    return {"label": label, "group": group, "chg5_pct": chg5}


def test_us_rotation_money_flow():
    us = [_sec("반도체·AI", "섹터", 2.1), _sec("2차전지·EV", "섹터", -5.6)]
    assert "반도체·AI" in _us_rotation(us) and "2차전지·EV" in _us_rotation(us)


def test_kr_read_broad_weakness_flags_worst():
    kr = [_sec("코스피", "지수", -7.1), _sec("코스닥", "지수", -11.9),
          _sec("현대차", "자동차", -21.6), _sec("삼성전자", "반도체", -4.1)]
    out = _kr_read(kr)
    assert "전반 약세" in out and "현대차" in out


def _flow(**kw):
    """Build a flow dict keyed by label from compact kwargs."""
    return {lbl: {"label": lbl, **vals} for lbl, vals in kw.items()}


def test_tilt_risk_off():
    f = _flow(**{
        "S&P 500": {"chg5_pct": -0.8},
        "VIX": {"chg5": 0.2},        # vol rising
        "HY spread": {"chg5_bp": 13},  # credit widening
    })
    assert _tilt(f) == "위험회피 우위 (주식↓·변동성↑·크레딧 부담↑)"


def test_tilt_risk_on():
    f = _flow(**{
        "S&P 500": {"chg5_pct": 1.2},
        "VIX": {"chg5": -1.5},
        "HY spread": {"chg5_bp": -8},
    })
    assert _tilt(f) == "위험선호 우위 (주식↑·변동성↓·크레딧 안정)"


def test_alert_fires_on_1d_extreme():
    f = _flow(**{"S&P 500": {"value": 7000, "chg1_pct": -2.4}})
    alerts = detect_alerts(f, None, [], {})
    assert any("S&P 500" in a and "-2.4%" in a for a in alerts)


def test_alert_silent_below_threshold():
    f = _flow(**{"S&P 500": {"value": 7000, "chg1_pct": -1.1}})
    assert detect_alerts(f, None, [], {}) == []


def test_alert_curve_flip_only_on_transition():
    rates = {"curve": "inverted", "spread_10y_2y": -0.05}
    # prior was upward → flip fires
    flips = detect_alerts({}, rates, [], {"curve": "upward"})
    assert any("커브 전환" in a for a in flips)
    # prior already inverted → no re-alert
    assert detect_alerts({}, rates, [], {"curve": "inverted"}) == []


def test_alert_new_crowded_excludes_basis_and_dedupes():
    pos = [
        {"market": "Japanese yen", "extreme": "crowded short", "basis": False},
        {"market": "S&P 500", "extreme": "crowded short", "basis": True},  # basis → never alerts
    ]
    # fresh extreme on yen fires; S&P basis excluded
    fired = detect_alerts({}, None, pos, {"extremes": {}})
    assert any("Japanese yen" in a for a in fired)
    assert not any("S&P 500" in a for a in fired)
    # already-known yen extreme → no re-alert
    assert detect_alerts({}, None, pos, {"extremes": {"Japanese yen": "crowded short"}}) == []
