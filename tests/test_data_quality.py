"""Unit tests for reusable data-quality checks."""

from __future__ import annotations

import pandas as pd

from src.data_quality import (
    duplicate_primary_key_mask,
    foreign_key_mask,
    quote_date_sequence_mask,
    valid_mileage_mask,
    valid_quote_amount_mask,
)


def test_duplicate_detection_marks_all_duplicate_keys() -> None:
    frame = pd.DataFrame({"id": ["A", "B", "B", "C"]})
    assert duplicate_primary_key_mask(frame, "id").tolist() == [
        False,
        True,
        True,
        False,
    ]


def test_vehicle_mileage_validity_boundaries() -> None:
    values = pd.Series([-1, 0, 500_000, 500_001, None])
    assert valid_mileage_mask(values).tolist() == [False, True, True, False, False]


def test_quote_amount_validity() -> None:
    values = pd.Series([-1, 0, 1, 500_000, 500_001, None])
    assert valid_quote_amount_mask(values).tolist() == [
        False,
        False,
        True,
        True,
        False,
        False,
    ]


def test_foreign_key_consistency_allows_null_optional_key() -> None:
    child = pd.Series(["D0001", "D9999", None])
    parent = pd.Series(["D0001", "D0002"])
    assert foreign_key_mask(child, parent).tolist() == [True, False, True]


def test_quote_date_consistency() -> None:
    quote_dates = pd.Series(["2025-01-02", "2025-01-01", "bad-date"])
    inquiry_dates = pd.Series(["2025-01-01", "2025-01-02", "2025-01-01"])
    assert quote_date_sequence_mask(quote_dates, inquiry_dates).tolist() == [
        True,
        False,
        False,
    ]
