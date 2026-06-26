"""Morning brief logic — alert triggers + tilt classifier. Pure, offline (no network)."""

from engine.brief import _tilt, detect_alerts


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
