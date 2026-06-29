"""Fear & Greed composite math + data sanity guard — pure, offline."""

import engine.psych as psych
from engine.psych import _clamp, _label, _lerp, fear_greed
from engine.sectors import _MAX_1D, _MAX_5D, _sane


def test_lerp_clamps_and_inverts():
    assert _lerp(0, 0, 10, 0, 100) == 0
    assert _lerp(10, 0, 10, 0, 100) == 100
    assert _lerp(-5, 0, 10, 0, 100) == 0          # clamped low
    assert _lerp(50, 0, 10, 0, 100) == 100        # clamped high
    assert _lerp(12, 32, 12, 0, 100) == 100       # inverted range (low VIX = greed)
    assert _lerp(32, 32, 12, 0, 100) == 0


def test_clamp():
    assert _clamp(150, 0, 100) == 100
    assert _clamp(-3, 0, 100) == 0
    assert _clamp(50, 0, 100) == 50


def test_label_zones():
    assert _label(10) == "극단적 공포"
    assert _label(35) == "공포"
    assert _label(50) == "중립"
    assert _label(65) == "탐욕"
    assert _label(90) == "극단적 탐욕"


def test_sanity_drops_absurd_moves():
    assert _sane(5.2, _MAX_5D) == 5.2          # normal → kept
    assert _sane(-12.0, _MAX_5D) == -12.0      # real crisis move → kept
    assert _sane(5000.0, _MAX_5D) is None      # garbage → dropped
    assert _sane(-99.0, _MAX_1D) is None       # impossible 1d → dropped
    assert _sane(None, _MAX_5D) is None


def test_fear_greed_integrates_breadth_and_safehaven(monkeypatch):
    # offline: no FRED key, no crypto/yfinance network — inject the two new factors
    monkeypatch.setattr(psych.os, "environ", {})          # key=None → FRED signals skip
    monkeypatch.setattr(psych, "_crypto_fng", lambda: None)
    monkeypatch.setattr(psych, "_yf_factors",
                        lambda: {"breadth": (70, "20/28 50일선 위"),
                                 "safehaven": (8.0, "주식−채권 20일 +8.0%p")})
    d = fear_greed()
    names = {c["name"] for c in d["components"]}
    assert "시장 폭" in names and "안전자산 선호" in names
    breadth = next(c for c in d["components"] if c["name"] == "시장 폭")
    assert breadth["score"] == 70                          # breadth passes through as a %
    safe = next(c for c in d["components"] if c["name"] == "안전자산 선호")
    assert safe["score"] == 100                            # +8%p spread → max greed
