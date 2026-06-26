"""Fear & Greed composite math + data sanity guard — pure, offline."""

from engine.psych import _clamp, _label, _lerp
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
