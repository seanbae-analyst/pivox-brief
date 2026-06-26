"""Offline tests for 8-K event cadence (engine/cadence.py).

Pure synthesis over a list of 8-K filings — no network. Locks the trailing-window counts,
the pace classification vs the prior comparable window, the item-mix breakdown, and that every
output is descriptive (counts + basis), never a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.cadence import eight_k_cadence


@dataclass
class _F:
    filing_date: str
    items: str = ""
    form: str = "8-K"


def _days_ago(as_of: str, n: int) -> str:
    from datetime import date, timedelta
    return (date.fromisoformat(as_of) - timedelta(days=n)).isoformat()


AS_OF = "2026-06-26"


def test_none_when_no_8ks():
    assert eight_k_cadence([], as_of=AS_OF) is None
    assert eight_k_cadence([_F(filing_date="2026-06-01", form="10-K")], as_of=AS_OF) is None


def test_trailing_counts_and_days_since_last():
    fs = [
        _F(_days_ago(AS_OF, 10), "2.02,9.01"),
        _F(_days_ago(AS_OF, 40), "8.01"),
        _F(_days_ago(AS_OF, 100), "5.02"),
        _F(_days_ago(AS_OF, 400), "2.02,9.01"),   # prior-year window
    ]
    c = eight_k_cadence(fs, as_of=AS_OF)
    assert c["count_ttm"] == 3
    assert c["count_prior_ttm"] == 1
    assert c["count_90d"] == 2
    assert c["days_since_last"] == 10


def test_pace_elevated_vs_prior_year():
    recent = [_F(_days_ago(AS_OF, d), "8.01") for d in (10, 40, 80, 120, 160)]      # 5 in TTM
    prior = [_F(_days_ago(AS_OF, 400), "8.01")]                                      # 1 prior
    c = eight_k_cadence(recent + prior, as_of=AS_OF)
    assert c["pace"] == "elevated"
    assert "elevated" in c["observations"][0]


def test_pace_steady_when_comparable():
    fs = [_F(_days_ago(AS_OF, d), "2.02") for d in (30, 200)] + \
         [_F(_days_ago(AS_OF, d), "2.02") for d in (400, 560)]
    c = eight_k_cadence(fs, as_of=AS_OF)
    assert c["pace"] == "steady"


def test_item_mix_decoded_and_ranked():
    fs = [
        _F(_days_ago(AS_OF, 10), "2.02,9.01"),
        _F(_days_ago(AS_OF, 50), "2.02,9.01"),
        _F(_days_ago(AS_OF, 90), "5.02"),
    ]
    c = eight_k_cadence(fs, as_of=AS_OF)
    labels = {m["label"]: m["count"] for m in c["item_mix"]}
    assert labels["Results of operations"] == 2
    assert labels["Financial statements & exhibits"] == 2
    assert labels["Officer / director change"] == 1


def test_descriptive_only_no_verdict_language():
    fs = [_F(_days_ago(AS_OF, d), "8.01") for d in (10, 40, 80)]
    c = eight_k_cadence(fs, as_of=AS_OF)
    blob = " ".join(c["observations"]).lower()
    for banned in ("buy", "sell", "should", "avoid", "recommend"):
        assert banned not in blob
