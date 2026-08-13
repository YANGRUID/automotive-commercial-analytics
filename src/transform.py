"""Clean, conform, enrich, and quality-check the raw automotive data."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .config import PROCESSED_DIR, REFERENCE_DIR, ensure_project_directories
from .data_quality import (
    foreign_key_mask,
    quote_date_sequence_mask,
    serialize_records,
    valid_mileage_mask,
    valid_quote_amount_mask,
    validate_processed_tables,
    weighted_rate,
)
from .extract import extract_raw_data
from .utils import (
    configure_logging,
    normalize_string_series,
    require_columns,
    standardize_columns,
    write_csv,
)


LOGGER = configure_logging()
DETECTED_AT = "2026-01-01T00:00:00Z"

LEAD_SOURCES = [
    "Organic Search",
    "Paid Search",
    "Dealer Referral",
    "Social Media",
    "Direct",
    "Partner",
]
STATUSES = ["Converted", "Lost", "Expired", "Open"]
FUEL_TYPES = ["Petrol", "Diesel", "Hybrid", "Electric", "Unknown"]
VEHICLE_CONDITIONS = ["Excellent", "Good", "Fair", "Poor"]


class QualityTracker:
    """Collect rejected records and issue-level corrective-action evidence."""

    def __init__(self) -> None:
        self._quarantine_parts: list[pd.DataFrame] = []
        self._issues: list[dict[str, object]] = []
        self.corrections: defaultdict[str, int] = defaultdict(int)
        self.duplicates: defaultdict[str, int] = defaultdict(int)

    def record_issue(
        self,
        table_name: str,
        issue_type: str,
        affected_rows: int,
        action: str,
        final_result: str,
    ) -> None:
        """Record an issue summary when one or more rows were affected."""

        if affected_rows <= 0:
            return
        self._issues.append(
            {
                "table_name": table_name,
                "issue_type": issue_type,
                "affected_rows": int(affected_rows),
                "action": action,
                "final_result": final_result,
            }
        )

    def quarantine(
        self,
        table_name: str,
        frame: pd.DataFrame,
        mask: pd.Series,
        id_column: str,
        issue_type: str,
        action: str,
    ) -> pd.DataFrame:
        """Capture rejected rows and return the retained frame."""

        mask = mask.fillna(True).astype(bool)
        rejected = frame.loc[mask].copy()
        if rejected.empty:
            return frame.copy()
        payload = serialize_records(rejected)
        part = pd.DataFrame(
            {
                "table_name": table_name,
                "record_id": rejected[id_column].astype("string").fillna("<NULL>"),
                "issue_type": issue_type,
                "action": action,
                "detected_at": DETECTED_AT,
                "record_payload": payload.to_numpy(),
            }
        )
        self._quarantine_parts.append(part)
        self.record_issue(
            table_name,
            issue_type,
            len(rejected),
            action,
            f"{len(rejected):,} row(s) excluded from the curated layer",
        )
        return frame.loc[~mask].copy()

    def corrected(
        self,
        table_name: str,
        issue_type: str,
        count: int,
        action: str,
        final_result: str,
    ) -> None:
        """Record a non-rejecting corrective action."""

        if count <= 0:
            return
        self.corrections[table_name] += int(count)
        self.record_issue(table_name, issue_type, count, action, final_result)

    def deduplicate(
        self, table_name: str, frame: pd.DataFrame, key: str
    ) -> pd.DataFrame:
        """Keep the first deterministic primary-key occurrence and quarantine later rows."""

        duplicate_mask = frame[key].duplicated(keep="first")
        count = int(duplicate_mask.sum())
        self.duplicates[table_name] += count
        return self.quarantine(
            table_name,
            frame,
            duplicate_mask,
            key,
            "duplicate_primary_key",
            "Keep first occurrence; quarantine later duplicate",
        )

    def quarantine_frame(self) -> pd.DataFrame:
        """Return all quarantined records with deterministic identifiers."""

        columns = [
            "quarantine_id",
            "table_name",
            "record_id",
            "issue_type",
            "action",
            "detected_at",
            "record_payload",
        ]
        if not self._quarantine_parts:
            return pd.DataFrame(columns=columns)
        result = pd.concat(self._quarantine_parts, ignore_index=True)
        result.insert(
            0,
            "quarantine_id",
            [f"QR{value:07d}" for value in range(1, len(result) + 1)],
        )
        return result[columns]

    def issue_frame(self) -> pd.DataFrame:
        """Aggregate repeated issue entries into an operations-friendly log."""

        columns = [
            "issue_id",
            "table_name",
            "issue_type",
            "affected_rows",
            "action",
            "final_result",
        ]
        if not self._issues:
            return pd.DataFrame(columns=columns)
        result = pd.DataFrame(self._issues)
        result = (
            result.groupby(
                ["table_name", "issue_type", "action", "final_result"],
                as_index=False,
                observed=True,
            )["affected_rows"]
            .sum()
            .sort_values(["table_name", "issue_type"])
            .reset_index(drop=True)
        )
        result.insert(
            0,
            "issue_id",
            [f"DQ{value:04d}" for value in range(1, len(result) + 1)],
        )
        return result[columns]


def _canonicalize(series: pd.Series, allowed: Iterable[str]) -> pd.Series:
    """Map case/whitespace variants to an approved canonical vocabulary."""

    lookup = {value.casefold(): value for value in allowed}
    normalized = normalize_string_series(series)
    return normalized.str.casefold().map(lookup).astype("string")


def _to_boolean(series: pd.Series) -> pd.Series:
    """Parse common boolean representations without Python truthiness traps."""

    normalized = normalize_string_series(series).str.casefold()
    return normalized.isin({"true", "1", "yes", "y", "t"})


def _required_non_null_counts(raw_tables: dict[str, pd.DataFrame]) -> tuple[int, int]:
    required = {
        "dim_customer": [
            "customer_id",
            "customer_created_date",
            "age_group",
            "canton",
            "customer_type",
            "preferred_contact_method",
            "lead_source",
        ],
        "dim_vehicle": [
            "vehicle_id",
            "brand",
            "model",
            "vehicle_type",
            "fuel_type",
            "manufacture_year",
            "mileage_km",
            "estimated_market_value",
            "vehicle_condition",
        ],
        "dim_dealer": [
            "dealer_id",
            "dealer_name",
            "dealer_region",
            "dealer_type",
            "dealer_rating",
            "active_flag",
        ],
        "fact_inquiry": [
            "inquiry_id",
            "customer_id",
            "vehicle_id",
            "inquiry_date",
            "lead_source",
            "status",
            "conversion_flag",
        ],
        "fact_quote": [
            "quote_id",
            "inquiry_id",
            "dealer_id",
            "quote_date",
            "quote_amount",
            "response_time_hours",
            "quote_rank",
            "accepted_flag",
        ],
        "dim_date": ["date", "year", "quarter", "month", "month_name"],
    }
    passed = 0
    total = 0
    for name, columns in required.items():
        frame = raw_tables[name]
        passed += int(frame[columns].notna().sum().sum())
        total += int(len(frame) * len(columns))
    return passed, total


def _validity_counts(tables: dict[str, pd.DataFrame]) -> tuple[int, int]:
    """Return comparable domain-check counts for raw or processed tables."""

    validity_checks = [
        valid_mileage_mask(tables["dim_vehicle"]["mileage_km"]),
        pd.to_numeric(
            tables["dim_vehicle"]["estimated_market_value"], errors="coerce"
        ).gt(0),
        pd.to_numeric(
            tables["dim_vehicle"]["manufacture_year"], errors="coerce"
        ).between(1990, 2025),
        pd.to_numeric(tables["dim_dealer"]["dealer_rating"], errors="coerce").between(
            0, 5
        ),
        pd.to_datetime(tables["fact_inquiry"]["inquiry_date"], errors="coerce").notna(),
        valid_quote_amount_mask(tables["fact_quote"]["quote_amount"]),
        pd.to_datetime(tables["fact_quote"]["quote_date"], errors="coerce").notna(),
        pd.to_numeric(tables["fact_quote"]["response_time_hours"], errors="coerce").ge(
            0
        ),
    ]
    return (
        int(sum(check.sum() for check in validity_checks)),
        int(sum(len(check) for check in validity_checks)),
    )


def _uniqueness_counts(tables: dict[str, pd.DataFrame]) -> tuple[int, int]:
    """Return primary-key uniqueness counts at each declared table grain."""

    key_map = {
        "dim_customer": "customer_id",
        "dim_vehicle": "vehicle_id",
        "dim_dealer": "dealer_id",
        "fact_inquiry": "inquiry_id",
        "fact_quote": "quote_id",
        "dim_date": "date",
    }
    uniqueness_total = sum(len(tables[name]) for name in key_map)
    uniqueness_failed = sum(
        int(tables[name][key].duplicated(keep="first").sum())
        for name, key in key_map.items()
    )
    return uniqueness_total - uniqueness_failed, uniqueness_total


def _integrity_counts(tables: dict[str, pd.DataFrame]) -> tuple[int, int]:
    """Return comparable fact-to-parent key coverage counts."""

    customer_keys = tables["dim_customer"]["customer_id"].drop_duplicates()
    vehicle_keys = tables["dim_vehicle"]["vehicle_id"].drop_duplicates()
    dealer_keys = tables["dim_dealer"]["dealer_id"].drop_duplicates()
    inquiry_keys = tables["fact_inquiry"]["inquiry_id"].drop_duplicates()
    integrity_checks = [
        foreign_key_mask(tables["fact_inquiry"]["customer_id"], customer_keys),
        foreign_key_mask(tables["fact_inquiry"]["vehicle_id"], vehicle_keys),
        foreign_key_mask(tables["fact_quote"]["inquiry_id"], inquiry_keys),
        foreign_key_mask(tables["fact_quote"]["dealer_id"], dealer_keys),
        foreign_key_mask(tables["fact_inquiry"]["winning_dealer_id"], dealer_keys),
    ]
    return (
        int(sum(check.sum() for check in integrity_checks)),
        int(sum(len(check) for check in integrity_checks)),
    )


def _quality_metric_counts(
    tables: dict[str, pd.DataFrame],
) -> dict[str, tuple[int, int]]:
    """Calculate like-for-like quality dimensions for a pipeline stage."""

    return {
        "completeness_rate": _required_non_null_counts(tables),
        "validity_rate": _validity_counts(tables),
        "uniqueness_rate": _uniqueness_counts(tables),
        "referential_integrity_rate": _integrity_counts(tables),
    }


def _build_quality_metric_frame(
    raw: dict[str, pd.DataFrame], processed: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Create raw-versus-processed score rows for the operations dashboard."""

    stage_counts = {
        "Raw": _quality_metric_counts(raw),
        "Processed": _quality_metric_counts(processed),
    }
    descriptions = {
        "completeness_rate": "Required fields populated at the applicable table grain",
        "validity_rate": "Values conform to documented types, dates, and business ranges",
        "uniqueness_rate": "Primary-key rows are unique at the declared table grain",
        "referential_integrity_rate": "Fact foreign keys resolve to curated parent records",
    }
    rows: list[dict[str, object]] = []
    for stage, metrics in stage_counts.items():
        for metric_name, (passed, total) in metrics.items():
            rows.append(
                {
                    "metric_name": metric_name,
                    "stage": stage,
                    "passed_records": passed,
                    "total_records": total,
                    "rate": weighted_rate(passed, total),
                    "description": descriptions[metric_name],
                    "assessment_date": "2026-01-01",
                }
            )

    quality = pd.DataFrame(rows)
    for stage in ["Raw", "Processed"]:
        stage_rows = quality[quality["stage"].eq(stage)]
        total = int(stage_rows["total_records"].sum())
        passed = int(stage_rows["passed_records"].sum())
        quality = pd.concat(
            [
                quality,
                pd.DataFrame(
                    [
                        {
                            "metric_name": "overall_data_quality_score",
                            "stage": stage,
                            "passed_records": passed,
                            "total_records": total,
                            "rate": weighted_rate(passed, total),
                            "description": "Passed checks divided by applicable checks across all four dimensions",
                            "assessment_date": "2026-01-01",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    return quality.sort_values(["stage", "metric_name"]).reset_index(drop=True)


def transform_tables(
    raw_tables: dict[str, pd.DataFrame],
    processed_dir: Path = PROCESSED_DIR,
    write_output: bool = True,
) -> dict[str, pd.DataFrame]:
    """Transform raw tables into validated fact-constellation-ready tables."""

    ensure_project_directories()
    raw = {name: standardize_columns(frame) for name, frame in raw_tables.items()}
    tracker = QualityTracker()

    customers = raw["dim_customer"].copy()
    require_columns(
        customers,
        [
            "customer_id",
            "customer_created_date",
            "age_group",
            "canton",
            "customer_type",
            "preferred_contact_method",
            "lead_source",
        ],
        "dim_customer",
    )
    customers["customer_id"] = normalize_string_series(
        customers["customer_id"]
    ).str.upper()
    customers = tracker.deduplicate("dim_customer", customers, "customer_id")
    customers["customer_created_date"] = pd.to_datetime(
        customers["customer_created_date"], errors="coerce"
    )
    customers = tracker.quarantine(
        "dim_customer",
        customers,
        customers["customer_created_date"].isna(),
        "customer_id",
        "malformed_customer_date",
        "Quarantine because registration sequence cannot be validated",
    )
    for column in ["age_group", "customer_type", "preferred_contact_method"]:
        customers[column] = normalize_string_series(customers[column], title_case=True)
    customers["canton"] = normalize_string_series(customers["canton"]).str.upper()
    missing_canton = int(customers["canton"].isna().sum())
    customers["canton"] = customers["canton"].fillna("Unknown")
    tracker.corrected(
        "dim_customer",
        "missing_canton",
        missing_canton,
        "Replace missing optional geography with explicit Unknown member",
        "Rows retained; unknowns remain visible in reporting",
    )
    original_lead = customers["lead_source"].copy()
    customers["lead_source"] = _canonicalize(customers["lead_source"], LEAD_SOURCES)
    lead_corrections = int(
        original_lead.astype("string").ne(customers["lead_source"]).fillna(False).sum()
    )
    tracker.corrected(
        "dim_customer",
        "inconsistent_lead_source_text",
        lead_corrections,
        "Trim and case-normalize to approved lead-source values",
        "Canonical categories restored",
    )
    customers["customer_created_date"] = customers["customer_created_date"].dt.date

    vehicles = raw["dim_vehicle"].copy()
    vehicles["vehicle_id"] = normalize_string_series(vehicles["vehicle_id"]).str.upper()
    vehicles = tracker.deduplicate("dim_vehicle", vehicles, "vehicle_id")
    for column in ["brand", "model", "vehicle_type", "fuel_type", "vehicle_condition"]:
        vehicles[column] = normalize_string_series(vehicles[column])
    catalog_path = REFERENCE_DIR / "vehicle_catalog.csv"
    canonical_brands = (
        pd.read_csv(catalog_path)["brand"].drop_duplicates().tolist()
        if catalog_path.exists()
        else vehicles["brand"].dropna().str.title().drop_duplicates().tolist()
    )
    vehicles["brand"] = _canonicalize(vehicles["brand"], canonical_brands)
    vehicles["vehicle_type"] = normalize_string_series(
        vehicles["vehicle_type"], title_case=True
    )
    vehicles["vehicle_condition"] = _canonicalize(
        vehicles["vehicle_condition"], VEHICLE_CONDITIONS
    )
    vehicles["fuel_type"] = _canonicalize(vehicles["fuel_type"], FUEL_TYPES)
    missing_fuel = int(vehicles["fuel_type"].isna().sum())
    vehicles["fuel_type"] = vehicles["fuel_type"].fillna("Unknown")
    tracker.corrected(
        "dim_vehicle",
        "missing_fuel_type",
        missing_fuel,
        "Replace missing optional fuel type with explicit Unknown member",
        "Rows retained without inventing a fuel classification",
    )
    for column in ["manufacture_year", "mileage_km", "estimated_market_value"]:
        vehicles[column] = pd.to_numeric(vehicles[column], errors="coerce")
    negative_repair = vehicles["mileage_km"].lt(0) & vehicles["mileage_km"].abs().le(
        500_000
    )
    negative_count = int(negative_repair.sum())
    vehicles.loc[negative_repair, "mileage_km"] = vehicles.loc[
        negative_repair, "mileage_km"
    ].abs()
    tracker.corrected(
        "dim_vehicle",
        "negative_mileage_sign_error",
        negative_count,
        "Take absolute value only when magnitude remains inside the accepted domain",
        "Plausible sign errors corrected and retained",
    )
    vehicle_invalid = (
        ~valid_mileage_mask(vehicles["mileage_km"])
        | vehicles["estimated_market_value"].le(0)
        | vehicles["estimated_market_value"].isna()
        | ~vehicles["manufacture_year"].between(1990, 2025)
    )
    vehicles = tracker.quarantine(
        "dim_vehicle",
        vehicles,
        vehicle_invalid,
        "vehicle_id",
        "invalid_vehicle_domain",
        "Quarantine values that cannot be corrected without inventing business data",
    )
    vehicles["manufacture_year"] = vehicles["manufacture_year"].astype(int)
    vehicles["mileage_km"] = vehicles["mileage_km"].round().astype(int)
    vehicles["estimated_market_value"] = vehicles["estimated_market_value"].round(2)
    vehicles["mileage_bracket"] = pd.cut(
        vehicles["mileage_km"],
        bins=[-1, 25_000, 75_000, 125_000, 200_000, 500_000],
        labels=["0-25k", "25k-75k", "75k-125k", "125k-200k", "200k+"],
    ).astype("string")
    vehicles["market_value_band"] = pd.cut(
        vehicles["estimated_market_value"],
        bins=[0, 10_000, 25_000, 50_000, 80_000, np.inf],
        labels=["<10k", "10k-25k", "25k-50k", "50k-80k", "80k+"],
        right=False,
    ).astype("string")

    dealers = raw["dim_dealer"].copy()
    dealers["dealer_id"] = normalize_string_series(dealers["dealer_id"]).str.upper()
    dealers = tracker.deduplicate("dim_dealer", dealers, "dealer_id")
    for column in ["dealer_name", "dealer_region", "dealer_type"]:
        dealers[column] = normalize_string_series(dealers[column])
    whitespace_count = int(
        raw["dim_dealer"]["dealer_name"]
        .astype("string")
        .str.strip()
        .ne(raw["dim_dealer"]["dealer_name"].astype("string"))
        .sum()
    )
    tracker.corrected(
        "dim_dealer",
        "dealer_name_whitespace",
        whitespace_count,
        "Trim leading and trailing whitespace",
        "Dealer labels standardized",
    )
    dealers["dealer_rating"] = pd.to_numeric(dealers["dealer_rating"], errors="coerce")
    dealers["active_flag"] = _to_boolean(dealers["active_flag"])
    dealers = tracker.quarantine(
        "dim_dealer",
        dealers,
        ~dealers["dealer_rating"].between(0, 5),
        "dealer_id",
        "invalid_dealer_rating",
        "Quarantine rating outside the documented 0-5 range",
    )
    dealers["dealer_rating"] = dealers["dealer_rating"].round(2)

    inquiries = raw["fact_inquiry"].copy()
    for column in ["inquiry_id", "customer_id", "vehicle_id", "winning_dealer_id"]:
        inquiries[column] = normalize_string_series(inquiries[column]).str.upper()
    inquiries = tracker.deduplicate("fact_inquiry", inquiries, "inquiry_id")
    inquiries["inquiry_date"] = pd.to_datetime(
        inquiries["inquiry_date"], errors="coerce"
    )
    inquiries["lead_source"] = _canonicalize(inquiries["lead_source"], LEAD_SOURCES)
    inquiries["status"] = _canonicalize(inquiries["status"], STATUSES)
    inquiries["conversion_flag"] = _to_boolean(inquiries["conversion_flag"])
    inquiries["final_sale_price"] = pd.to_numeric(
        inquiries["final_sale_price"], errors="coerce"
    )
    inquiries["days_to_conversion"] = pd.to_numeric(
        inquiries["days_to_conversion"], errors="coerce"
    )
    malformed_inquiry_date = inquiries["inquiry_date"].isna()
    inquiries = tracker.quarantine(
        "fact_inquiry",
        inquiries,
        malformed_inquiry_date,
        "inquiry_id",
        "malformed_inquiry_date",
        "Quarantine because time-series placement and date sequence are unknown",
    )
    inquiry_fk_invalid = ~foreign_key_mask(
        inquiries["customer_id"], customers["customer_id"]
    ) | ~foreign_key_mask(inquiries["vehicle_id"], vehicles["vehicle_id"])
    inquiries = tracker.quarantine(
        "fact_inquiry",
        inquiries,
        inquiry_fk_invalid,
        "inquiry_id",
        "invalid_inquiry_foreign_key",
        "Quarantine orphan inquiry until the parent entity is repaired",
    )
    customer_created = inquiries["customer_id"].map(
        customers.set_index("customer_id")["customer_created_date"]
    )
    impossible_customer_sequence = inquiries["inquiry_date"].lt(
        pd.to_datetime(customer_created)
    )
    inquiries = tracker.quarantine(
        "fact_inquiry",
        inquiries,
        impossible_customer_sequence,
        "inquiry_id",
        "customer_date_sequence",
        "Quarantine inquiry dated before customer registration",
    )

    quotes = raw["fact_quote"].copy()
    for column in ["quote_id", "inquiry_id", "dealer_id"]:
        quotes[column] = normalize_string_series(quotes[column]).str.upper()
    quotes = tracker.deduplicate("fact_quote", quotes, "quote_id")
    quotes["quote_date"] = pd.to_datetime(quotes["quote_date"], errors="coerce")
    quotes["quote_amount"] = pd.to_numeric(quotes["quote_amount"], errors="coerce")
    quotes["response_time_hours"] = pd.to_numeric(
        quotes["response_time_hours"], errors="coerce"
    )
    quotes["accepted_flag"] = _to_boolean(quotes["accepted_flag"])
    invalid_quote_domain = quotes["quote_date"].isna() | ~valid_quote_amount_mask(
        quotes["quote_amount"]
    )
    quotes = tracker.quarantine(
        "fact_quote",
        quotes,
        invalid_quote_domain,
        "quote_id",
        "invalid_quote_domain",
        "Quarantine malformed dates or impossible monetary amounts",
    )
    quote_fk_invalid = ~foreign_key_mask(
        quotes["inquiry_id"], inquiries["inquiry_id"]
    ) | ~foreign_key_mask(quotes["dealer_id"], dealers["dealer_id"])
    quotes = tracker.quarantine(
        "fact_quote",
        quotes,
        quote_fk_invalid,
        "quote_id",
        "invalid_quote_foreign_key",
        "Quarantine orphan quote until dealer or inquiry key is repaired",
    )
    mapped_inquiry_date = quotes["inquiry_id"].map(
        inquiries.set_index("inquiry_id")["inquiry_date"]
    )
    invalid_sequence = ~quote_date_sequence_mask(
        quotes["quote_date"], mapped_inquiry_date
    )
    quotes = tracker.quarantine(
        "fact_quote",
        quotes,
        invalid_sequence,
        "quote_id",
        "quote_date_sequence",
        "Quarantine quote dated before its inquiry",
    )
    missing_response = quotes["response_time_hours"].isna()
    dealer_medians = quotes.groupby("dealer_id", observed=True)[
        "response_time_hours"
    ].transform("median")
    overall_median = float(quotes["response_time_hours"].median())
    quotes.loc[missing_response, "response_time_hours"] = dealer_medians.loc[
        missing_response
    ].fillna(overall_median)
    tracker.corrected(
        "fact_quote",
        "missing_response_time",
        int(missing_response.sum()),
        "Impute the dealer median, falling back to the portfolio median",
        "Rows retained; imputation rule documented and reproducible",
    )

    # Reconcile accepted quotes to inquiry outcomes after any rejected quote rows.
    accepted = quotes.loc[
        quotes["accepted_flag"], ["inquiry_id", "dealer_id", "quote_amount"]
    ]
    accepted_counts = accepted.groupby("inquiry_id", observed=True).size()
    converted_mask = inquiries["conversion_flag"]
    missing_accepted = converted_mask & inquiries["inquiry_id"].map(
        accepted_counts
    ).fillna(0).ne(1)
    downgraded_count = int(missing_accepted.sum())
    inquiries.loc[missing_accepted, "conversion_flag"] = False
    inquiries.loc[missing_accepted, "status"] = "Lost"
    inquiries.loc[
        missing_accepted,
        ["final_sale_price", "winning_dealer_id", "days_to_conversion"],
    ] = [np.nan, pd.NA, np.nan]
    tracker.corrected(
        "fact_inquiry",
        "accepted_quote_removed_by_quality_rule",
        downgraded_count,
        "Downgrade conversion when its accepted quote is not loadable",
        "Fact tables remain internally consistent; affected outcomes are not overstated",
    )
    accepted = accepted.drop_duplicates("inquiry_id").set_index("inquiry_id")
    converted_mask = inquiries["conversion_flag"]
    mapped_winner = inquiries.loc[converted_mask, "inquiry_id"].map(
        accepted["dealer_id"]
    )
    winner_corrections = int(
        inquiries.loc[converted_mask, "winning_dealer_id"]
        .astype("string")
        .ne(mapped_winner.astype("string"))
        .sum()
    )
    inquiries.loc[converted_mask, "winning_dealer_id"] = mapped_winner.to_numpy()
    inquiries.loc[converted_mask, "final_sale_price"] = (
        inquiries.loc[converted_mask, "inquiry_id"]
        .map(accepted["quote_amount"])
        .to_numpy()
    )
    tracker.corrected(
        "fact_inquiry",
        "winning_dealer_mismatch",
        winner_corrections,
        "Derive winner and final sale price from the single accepted quote",
        "Commercial outcomes reconciled across both fact tables",
    )
    inquiries.loc[~inquiries["conversion_flag"], "winning_dealer_id"] = pd.NA
    inquiries.loc[~inquiries["conversion_flag"], "final_sale_price"] = np.nan
    inquiries.loc[~inquiries["conversion_flag"], "days_to_conversion"] = np.nan

    quotes["quote_rank"] = (
        quotes.groupby("inquiry_id", observed=True)["quote_amount"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    inquiry_vehicle = inquiries.set_index("inquiry_id")["vehicle_id"]
    vehicle_market = vehicles.set_index("vehicle_id")["estimated_market_value"]
    quotes["estimated_market_value"] = (
        quotes["inquiry_id"].map(inquiry_vehicle).map(vehicle_market)
    )
    quotes["quote_to_market_ratio"] = (
        quotes["quote_amount"] / quotes["estimated_market_value"]
    ).round(4)
    # Soft business threshold: retain the quote for analysis, but surface unusually
    # low/high competitiveness relative to the appraised market value.
    quotes["anomaly_flag"] = ~quotes["quote_to_market_ratio"].between(0.70, 1.08)
    anomaly_count = int(quotes["anomaly_flag"].sum())
    tracker.record_issue(
        "fact_quote",
        "quote_to_market_anomaly",
        anomaly_count,
        "Retain plausible positive quote and set anomaly_flag for review",
        "Outliers remain analytically visible without contaminating hard-validity checks",
    )

    quote_summary = quotes.groupby("inquiry_id", observed=True).agg(
        quote_count=("quote_id", "count"),
        highest_quote=("quote_amount", "max"),
        lowest_quote=("quote_amount", "min"),
        average_quote=("quote_amount", "mean"),
        fastest_response_hours=("response_time_hours", "min"),
    )
    quote_summary["quote_spread"] = (
        quote_summary["highest_quote"] - quote_summary["lowest_quote"]
    )
    quote_summary["quote_spread_pct"] = (
        quote_summary["quote_spread"] / quote_summary["lowest_quote"]
    )
    inquiries = inquiries.merge(
        quote_summary, how="inner", left_on="inquiry_id", right_index=True
    )
    manufacture_year = inquiries["vehicle_id"].map(
        vehicles.set_index("vehicle_id")["manufacture_year"]
    )
    inquiries["vehicle_age_at_inquiry"] = (
        inquiries["inquiry_date"].dt.year - manufacture_year
    ).astype(int)
    inquiries["inquiry_date"] = inquiries["inquiry_date"].dt.date
    quotes["quote_date"] = quotes["quote_date"].dt.date
    quotes["quote_amount"] = quotes["quote_amount"].round(2)
    quotes["response_time_hours"] = quotes["response_time_hours"].round(2)
    inquiries["final_sale_price"] = inquiries["final_sale_price"].round(2)
    inquiries["days_to_conversion"] = inquiries["days_to_conversion"].astype("Int64")
    for column in [
        "highest_quote",
        "lowest_quote",
        "average_quote",
        "quote_spread",
        "fastest_response_hours",
        "quote_spread_pct",
    ]:
        inquiries[column] = inquiries[column].round(
            2 if column != "quote_spread_pct" else 4
        )

    dates = raw["dim_date"].copy()
    dates["date"] = pd.to_datetime(dates["date"], errors="coerce")
    dates = tracker.quarantine(
        "dim_date",
        dates,
        dates["date"].isna() | dates["date"].duplicated(keep="first"),
        "date",
        "invalid_date_dimension_key",
        "Quarantine malformed or duplicate calendar key",
    )
    dates["year"] = dates["date"].dt.year
    dates["quarter"] = "Q" + dates["date"].dt.quarter.astype(str)
    dates["month"] = dates["date"].dt.month
    dates["month_name"] = dates["date"].dt.month_name()
    dates["week"] = dates["date"].dt.isocalendar().week.astype(int)
    dates["day_of_week"] = dates["date"].dt.day_name()
    dates["is_weekend"] = dates["date"].dt.dayofweek.ge(5)
    dates["date"] = dates["date"].dt.date

    curated: dict[str, pd.DataFrame] = {
        "dim_customer": customers.reset_index(drop=True),
        "dim_vehicle": vehicles.reset_index(drop=True),
        "dim_dealer": dealers.reset_index(drop=True),
        "fact_inquiry": inquiries.reset_index(drop=True),
        "fact_quote": quotes.reset_index(drop=True),
        "dim_date": dates.reset_index(drop=True),
    }
    validate_processed_tables(curated)
    quality_metrics = _build_quality_metric_frame(raw, curated)
    quarantine = tracker.quarantine_frame()
    issue_log = tracker.issue_frame()

    summary_rows = []
    for table_name in [
        "dim_customer",
        "dim_vehicle",
        "dim_dealer",
        "fact_inquiry",
        "fact_quote",
        "dim_date",
    ]:
        rejected_unique = int(
            quarantine.loc[
                quarantine["table_name"].eq(table_name), "record_id"
            ].nunique()
        )
        summary_rows.append(
            {
                "table_name": table_name,
                "raw_records": len(raw[table_name]),
                "duplicate_records": tracker.duplicates[table_name],
                "corrected_records": tracker.corrections[table_name],
                "quarantined_records": rejected_unique,
                "clean_records": len(curated[table_name]),
                "loaded_records": 0,
                "load_status": "Ready",
            }
        )
    pipeline_summary = pd.DataFrame(summary_rows)
    curated.update(
        {
            "data_quality_metrics": quality_metrics,
            "data_quality_issue_log": issue_log,
            "quarantined_records": quarantine,
            "pipeline_run_summary": pipeline_summary,
        }
    )

    if write_output:
        for table_name, frame in curated.items():
            write_csv(frame, processed_dir / f"{table_name}.csv")
            LOGGER.info("Wrote processed %-23s %9s rows", table_name, f"{len(frame):,}")
    return curated


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    args = parser.parse_args()
    raw = extract_raw_data()
    transformed = transform_tables(raw, args.processed_dir)
    LOGGER.info(
        "Transformation complete: %s inquiries and %s quotes ready for loading",
        f"{len(transformed['fact_inquiry']):,}",
        f"{len(transformed['fact_quote']):,}",
    )


if __name__ == "__main__":
    main()
