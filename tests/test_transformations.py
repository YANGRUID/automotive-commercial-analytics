"""Tests for core standardization and end-to-end transformation behavior."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.transform import transform_tables
from src.utils import standardize_columns


def _minimal_raw_tables() -> dict[str, pd.DataFrame]:
    customers = pd.DataFrame(
        [
            {
                "customer_id": "C000001",
                "customer_created_date": "2021-01-01",
                "age_group": "25-34",
                "canton": None,
                "customer_type": "Private",
                "preferred_contact_method": "Email",
                "lead_source": "  dealer referral ",
            },
            {
                "customer_id": "C000001",
                "customer_created_date": "2021-01-01",
                "age_group": "25-34",
                "canton": "ZH",
                "customer_type": "Private",
                "preferred_contact_method": "Email",
                "lead_source": "Dealer Referral",
            },
        ]
    )
    vehicles = pd.DataFrame(
        [
            {
                "vehicle_id": "V0000001",
                "brand": " volkswagen ",
                "model": "Golf",
                "vehicle_type": "Hatchback",
                "fuel_type": "Petrol",
                "manufacture_year": 2020,
                "mileage_km": -5_000,
                "estimated_market_value": 25_000,
                "vehicle_condition": "Good",
            }
        ]
    )
    dealers = pd.DataFrame(
        [
            {
                "dealer_id": "D0001",
                "dealer_name": " Zurich Autohaus 001 ",
                "dealer_region": "Zurich",
                "dealer_type": "Franchise",
                "dealer_rating": 4.5,
                "active_flag": True,
            },
            {
                "dealer_id": "D0002",
                "dealer_name": "Bern Autohaus 002",
                "dealer_region": "Espace Mittelland",
                "dealer_type": "Independent",
                "dealer_rating": 4.0,
                "active_flag": True,
            },
        ]
    )
    inquiries = pd.DataFrame(
        [
            {
                "inquiry_id": "I0000001",
                "customer_id": "C000001",
                "vehicle_id": "V0000001",
                "inquiry_date": "2022-01-01",
                "lead_source": "dealer referral",
                "status": " converted ",
                "final_sale_price": 24_000,
                "winning_dealer_id": "D9999",
                "conversion_flag": True,
                "days_to_conversion": 2,
            }
        ]
    )
    quotes = pd.DataFrame(
        [
            {
                "quote_id": "Q00000001",
                "inquiry_id": "I0000001",
                "dealer_id": "D0001",
                "quote_date": "2022-01-01",
                "quote_amount": 24_000,
                "response_time_hours": 4,
                "quote_rank": 1,
                "accepted_flag": True,
            },
            {
                "quote_id": "Q00000002",
                "inquiry_id": "I0000001",
                "dealer_id": "D0002",
                "quote_date": "2022-01-02",
                "quote_amount": 22_000,
                "response_time_hours": None,
                "quote_rank": 2,
                "accepted_flag": False,
            },
        ]
    )
    dates = pd.DataFrame(
        {
            "date": ["2022-01-01", "2022-01-02"],
            "year": [2022, 2022],
            "quarter": ["Q1", "Q1"],
            "month": [1, 1],
            "month_name": ["January", "January"],
            "week": [52, 52],
            "day_of_week": ["Saturday", "Sunday"],
            "is_weekend": [True, True],
        }
    )
    return {
        "dim_customer": customers,
        "dim_vehicle": vehicles,
        "dim_dealer": dealers,
        "fact_inquiry": inquiries,
        "fact_quote": quotes,
        "dim_date": dates,
    }


def test_standardize_columns() -> None:
    frame = pd.DataFrame(columns=[" Customer ID ", "Quote-Amount (CHF)"])
    result = standardize_columns(frame)
    assert result.columns.tolist() == ["customer_id", "quote_amount_chf"]


def test_transform_tables_corrects_and_enriches() -> None:
    transformed = transform_tables(_minimal_raw_tables(), write_output=False)

    assert len(transformed["dim_customer"]) == 1
    assert transformed["dim_customer"].iloc[0]["canton"] == "Unknown"
    assert transformed["dim_customer"].iloc[0]["lead_source"] == "Dealer Referral"
    assert transformed["dim_vehicle"].iloc[0]["brand"] == "Volkswagen"
    assert transformed["dim_vehicle"].iloc[0]["mileage_km"] == 5_000

    inquiry = transformed["fact_inquiry"].iloc[0]
    assert inquiry["winning_dealer_id"] == "D0001"
    assert inquiry["quote_count"] == 2
    assert inquiry["quote_spread"] == 2_000
    assert inquiry["vehicle_age_at_inquiry"] == 2

    quote = transformed["fact_quote"].set_index("quote_id").loc["Q00000002"]
    assert pd.notna(quote["response_time_hours"])
    assert quote["quote_to_market_ratio"] == 0.88
    assert not quote["anomaly_flag"]


def test_transform_records_duplicates_and_corrections() -> None:
    transformed = transform_tables(_minimal_raw_tables(), write_output=False)
    issues = transformed["data_quality_issue_log"]
    issue_types = set(issues["issue_type"])
    assert "duplicate_primary_key" in issue_types
    assert "missing_canton" in issue_types
    assert "negative_mileage_sign_error" in issue_types
    assert "winning_dealer_mismatch" in issue_types


def test_quality_scores_reconcile_to_persisted_check_counts() -> None:
    transformed = transform_tables(_minimal_raw_tables(), write_output=False)
    metrics = transformed["data_quality_metrics"]

    expected_rate = metrics["passed_records"] / metrics["total_records"]
    assert np.allclose(metrics["rate"], expected_rate)

    for stage in ["Raw", "Processed"]:
        stage_rows = metrics.loc[
            metrics["stage"].eq(stage)
            & metrics["metric_name"].ne("overall_data_quality_score")
        ]
        overall = metrics.loc[
            metrics["stage"].eq(stage)
            & metrics["metric_name"].eq("overall_data_quality_score")
        ].iloc[0]
        assert overall["passed_records"] == stage_rows["passed_records"].sum()
        assert overall["total_records"] == stage_rows["total_records"].sum()
