"""Reusable data-quality rules, metrics, and processed-data assertions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class QualityMetric:
    """One auditable data-quality metric result."""

    metric_name: str
    passed_records: int
    total_records: int
    rate: float
    description: str


def duplicate_primary_key_mask(frame: pd.DataFrame, key: str) -> pd.Series:
    """Return a mask identifying every row with a duplicated primary key."""

    return frame[key].duplicated(keep=False)


def valid_mileage_mask(series: pd.Series) -> pd.Series:
    """Return whether vehicle mileage is inside the documented domain."""

    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.between(0, 500_000, inclusive="both")


def valid_quote_amount_mask(series: pd.Series) -> pd.Series:
    """Return whether a quote is positive and below the hard plausibility ceiling."""

    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.gt(0) & numeric.le(500_000)


def foreign_key_mask(child: pd.Series, parent: pd.Series) -> pd.Series:
    """Return whether each non-null child key exists in the parent key set."""

    parent_keys = set(parent.dropna().astype(str))
    child_values = child.astype("string")
    return child_values.isna() | child_values.astype(str).isin(parent_keys)


def quote_date_sequence_mask(
    quote_dates: pd.Series, inquiry_dates: pd.Series
) -> pd.Series:
    """Return whether quotes occur on or after their inquiries."""

    quote_dt = pd.to_datetime(quote_dates, errors="coerce")
    inquiry_dt = pd.to_datetime(inquiry_dates, errors="coerce")
    return quote_dt.notna() & inquiry_dt.notna() & quote_dt.ge(inquiry_dt)


def accepted_quote_rule_violations(
    inquiries: pd.DataFrame, quotes: pd.DataFrame
) -> pd.DataFrame:
    """Return inquiries that violate the one-winner accepted-quote rule."""

    accepted_counts = (
        quotes.assign(accepted_flag=quotes["accepted_flag"].astype(bool))
        .groupby("inquiry_id", observed=True)["accepted_flag"]
        .sum()
        .rename("accepted_count")
    )
    check = inquiries[["inquiry_id", "conversion_flag", "winning_dealer_id"]].merge(
        accepted_counts, how="left", left_on="inquiry_id", right_index=True
    )
    check["accepted_count"] = check["accepted_count"].fillna(0).astype(int)
    converted = check["conversion_flag"].astype(bool)
    invalid_count = (converted & check["accepted_count"].ne(1)) | (
        ~converted & check["accepted_count"].ne(0)
    )

    accepted_dealer = (
        quotes.loc[quotes["accepted_flag"].astype(bool), ["inquiry_id", "dealer_id"]]
        .drop_duplicates("inquiry_id")
        .set_index("inquiry_id")["dealer_id"]
    )
    check["accepted_dealer_id"] = check["inquiry_id"].map(accepted_dealer)
    invalid_winner = converted & check["winning_dealer_id"].astype("string").ne(
        check["accepted_dealer_id"].astype("string")
    )
    return check.loc[invalid_count | invalid_winner].copy()


def metric_frame(metrics: list[QualityMetric]) -> pd.DataFrame:
    """Convert quality metrics to the persisted table shape."""

    rows = [metric.__dict__ for metric in metrics]
    return pd.DataFrame(rows)


def weighted_rate(passed_records: int, total_records: int) -> float:
    """Calculate a bounded quality rate, treating an empty check as perfect."""

    if total_records == 0:
        return 1.0
    return float(np.clip(passed_records / total_records, 0.0, 1.0))


def serialize_records(frame: pd.DataFrame) -> pd.Series:
    """Serialize a small set of quarantined rows for auditability."""

    safe = frame.astype("string").fillna("<NULL>")
    return safe.apply(
        lambda row: json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True),
        axis=1,
    )


def validate_processed_tables(tables: Mapping[str, pd.DataFrame]) -> dict[str, int]:
    """Assert the critical rules required before database loading."""

    customers = tables["dim_customer"]
    vehicles = tables["dim_vehicle"]
    dealers = tables["dim_dealer"]
    dates = tables["dim_date"]
    inquiries = tables["fact_inquiry"]
    quotes = tables["fact_quote"]

    quote_summary = quotes.groupby("inquiry_id", observed=True).agg(
        quote_count=("quote_id", "count"),
        highest_quote=("quote_amount", "max"),
        lowest_quote=("quote_amount", "min"),
        average_quote=("quote_amount", "mean"),
        fastest_response_hours=("response_time_hours", "min"),
    )
    inquiry_summary = inquiries.set_index("inquiry_id")
    summary_checks = [
        inquiry_summary["quote_count"].eq(quote_summary["quote_count"]),
        np.isclose(inquiry_summary["highest_quote"], quote_summary["highest_quote"]),
        np.isclose(inquiry_summary["lowest_quote"], quote_summary["lowest_quote"]),
        np.isclose(
            inquiry_summary["average_quote"], quote_summary["average_quote"], atol=0.01
        ),
        np.isclose(
            inquiry_summary["fastest_response_hours"],
            quote_summary["fastest_response_hours"],
            atol=0.01,
        ),
    ]
    summary_reconciles = all(np.asarray(check).all() for check in summary_checks)

    accepted_values = (
        quotes.loc[quotes["accepted_flag"].astype(bool), ["inquiry_id", "quote_amount"]]
        .drop_duplicates("inquiry_id")
        .set_index("inquiry_id")["quote_amount"]
    )
    converted = inquiries.loc[
        inquiries["conversion_flag"].astype(bool), ["inquiry_id", "final_sale_price"]
    ].set_index("inquiry_id")
    accepted_value_reconciles = np.isclose(
        converted["final_sale_price"], converted.index.map(accepted_values), atol=0.01
    ).all()

    date_keys = pd.to_datetime(dates["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    inquiry_dates = pd.to_datetime(
        inquiries["inquiry_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    quote_dates = pd.to_datetime(quotes["quote_date"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )

    assertions = {
        "unique_customer_id": int(~customers["customer_id"].duplicated().any()),
        "unique_vehicle_id": int(~vehicles["vehicle_id"].duplicated().any()),
        "unique_dealer_id": int(~dealers["dealer_id"].duplicated().any()),
        "unique_inquiry_id": int(~inquiries["inquiry_id"].duplicated().any()),
        "unique_quote_id": int(~quotes["quote_id"].duplicated().any()),
        "unique_date": int(~dates["date"].duplicated().any()),
        "valid_mileage": int(valid_mileage_mask(vehicles["mileage_km"]).all()),
        "valid_manufacture_year": int(
            pd.to_numeric(vehicles["manufacture_year"], errors="coerce")
            .between(1990, 2025)
            .all()
        ),
        "valid_dealer_rating": int(
            pd.to_numeric(dealers["dealer_rating"], errors="coerce").between(0, 5).all()
        ),
        "valid_quote_amount": int(
            valid_quote_amount_mask(quotes["quote_amount"]).all()
        ),
        "valid_response_time": int(
            pd.to_numeric(quotes["response_time_hours"], errors="coerce").ge(0).all()
        ),
        "inquiry_customer_fk": int(
            foreign_key_mask(inquiries["customer_id"], customers["customer_id"]).all()
        ),
        "inquiry_vehicle_fk": int(
            foreign_key_mask(inquiries["vehicle_id"], vehicles["vehicle_id"]).all()
        ),
        "quote_inquiry_fk": int(
            foreign_key_mask(quotes["inquiry_id"], inquiries["inquiry_id"]).all()
        ),
        "quote_dealer_fk": int(
            foreign_key_mask(quotes["dealer_id"], dealers["dealer_id"]).all()
        ),
        "inquiry_date_fk": int(foreign_key_mask(inquiry_dates, date_keys).all()),
        "quote_date_fk": int(foreign_key_mask(quote_dates, date_keys).all()),
        "quote_date_sequence": int(
            quote_date_sequence_mask(
                quotes["quote_date"],
                quotes["inquiry_id"].map(
                    inquiries.set_index("inquiry_id")["inquiry_date"]
                ),
            ).all()
        ),
        "accepted_quote_rule": int(
            accepted_quote_rule_violations(inquiries, quotes).empty
        ),
        "conversion_status_consistency": int(
            inquiries["status"]
            .eq("Converted")
            .eq(inquiries["conversion_flag"].astype(bool))
            .all()
        ),
        "accepted_value_reconciliation": int(accepted_value_reconciles),
        "quote_summary_reconciliation": int(summary_reconciles),
    }
    failed = [name for name, passed in assertions.items() if not passed]
    if failed:
        raise ValueError(f"Critical processed-data checks failed: {failed}")
    return assertions
