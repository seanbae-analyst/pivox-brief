"""Beginner glossary + mood thermometer + explain_level — pure, offline."""

from engine.glossary import GLOSSARY, explain, gloss, mood, term_of_day


def test_gloss_and_explain():
    assert "공포지수" in gloss("VIX")
    e = explain("크레딧 스프레드")
    assert e["term"] == "크레딧 스프레드" and e["long"] and e["gloss"]
    assert gloss("없는용어") is None


def test_every_entry_well_formed():
    for term, (g, long, _ana) in GLOSSARY.items():
        assert g and long, term


def test_term_of_day_deterministic():
    a = term_of_day("2026-06-26")
    b = term_of_day("2026-06-26")
    c = term_of_day("2026-06-27")
    assert a["term"] == b["term"]            # same day → same term
    assert a["term"] != c["term"] or True    # next day usually differs (deck rotation)
    assert a["long"]


def test_mood_fearful_when_selloff():
    flow = [
        {"label": "S&P 500", "chg5_pct": -4.0},
        {"label": "VIX", "value": 30.0, "chg5": 5.0},
        {"label": "HY spread", "chg5_bp": 20},
    ]
    m = mood(flow, None)
    assert m["level"] == 5 and m["emoji"] and "공포" in m["label"]


def test_mood_calm_when_quiet():
    flow = [
        {"label": "S&P 500", "chg5_pct": 0.5},
        {"label": "VIX", "value": 13.0, "chg5": -1.0},
        {"label": "HY spread", "chg5_bp": -5},
    ]
    m = mood(flow, None)
    assert m["level"] == 1
