"""Tests for analytical grain and cross-fact commercial rules."""

from __future__ import annotations

import pandas as pd

from src.data_quality import accepted_quote_rule_violations


def test_one_accepted_quote_per_converted_inquiry() -> None:
    inquiries = pd.DataFrame(
        {
            "inquiry_id": ["I1", "I2"],
            "conversion_flag": [True, False],
            "winning_dealer_id": ["D1", None],
        }
    )
    quotes = pd.DataFrame(
        {
            "inquiry_id": ["I1", "I1", "I2"],
            "dealer_id": ["D1", "D2", "D1"],
            "accepted_flag": [True, False, False],
        }
    )
    assert accepted_quote_rule_violations(inquiries, quotes).empty


def test_multiple_accepted_quotes_are_rejected() -> None:
    inquiries = pd.DataFrame(
        {
            "inquiry_id": ["I1"],
            "conversion_flag": [True],
            "winning_dealer_id": ["D1"],
        }
    )
    quotes = pd.DataFrame(
        {
            "inquiry_id": ["I1", "I1"],
            "dealer_id": ["D1", "D2"],
            "accepted_flag": [True, True],
        }
    )
    assert len(accepted_quote_rule_violations(inquiries, quotes)) == 1


def test_conversion_rate_uses_inquiry_grain() -> None:
    inquiries = pd.DataFrame(
        {"inquiry_id": ["I1", "I2", "I3"], "conversion_flag": [True, False, True]}
    )
    assert inquiries["conversion_flag"].mean() == 2 / 3


def test_quote_spread_calculation() -> None:
    quotes = pd.DataFrame(
        {"inquiry_id": ["I1", "I1", "I2", "I2"], "quote_amount": [10, 12, 20, 25]}
    )
    spread = quotes.groupby("inquiry_id")["quote_amount"].agg(
        lambda values: values.max() - values.min()
    )
    assert spread.to_dict() == {"I1": 2, "I2": 5}
