"""Create reproducible KPI evidence from the curated analytical tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import PROCESSED_DIR, ensure_project_directories
from .utils import configure_logging, write_csv


LOGGER = configure_logging()


def load_curated_data(processed_dir: Path = PROCESSED_DIR) -> dict[str, pd.DataFrame]:
    """Load curated tables at their documented analytical grains."""

    return {
        "inquiries": pd.read_csv(
            processed_dir / "fact_inquiry.csv", parse_dates=["inquiry_date"]
        ),
        "quotes": pd.read_csv(
            processed_dir / "fact_quote.csv", parse_dates=["quote_date"]
        ),
        "vehicles": pd.read_csv(processed_dir / "dim_vehicle.csv"),
        "dealers": pd.read_csv(processed_dir / "dim_dealer.csv"),
        "quality": pd.read_csv(processed_dir / "data_quality_metrics.csv"),
        "issues": pd.read_csv(processed_dir / "data_quality_issue_log.csv"),
    }


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a small analytical table into JSON-compatible records."""

    safe = frame.copy()
    for column in safe.select_dtypes(include=["datetime", "datetimetz"]).columns:
        safe[column] = safe[column].dt.strftime("%Y-%m-%d")
    return json.loads(safe.to_json(orient="records", date_format="iso"))


def _wilson_interval(
    successes: pd.Series, totals: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """Return 95% Wilson intervals for binomial rates without extra dependencies."""

    z = 1.959963984540054
    rate = successes / totals
    denominator = 1 + z**2 / totals
    centre = (rate + z**2 / (2 * totals)) / denominator
    margin = (
        z * np.sqrt(rate * (1 - rate) / totals + z**2 / (4 * totals**2)) / denominator
    )
    return centre - margin, centre + margin


def calculate_analysis_summary(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Calculate management KPIs and evidence tables from curated data."""

    inquiries = tables["inquiries"].copy()
    quotes = tables["quotes"].copy()
    vehicles = tables["vehicles"]
    dealers = tables["dealers"]
    quality = tables["quality"]

    monthly = (
        inquiries.assign(
            month=inquiries["inquiry_date"].dt.to_period("M").dt.to_timestamp()
        )
        .groupby("month", observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversions=("conversion_flag", "sum"),
            conversion_rate=("conversion_flag", "mean"),
            accepted_value=("final_sale_price", "sum"),
        )
        .reset_index()
    )
    lead = (
        inquiries.groupby("lead_source", observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversions=("conversion_flag", "sum"),
            conversion_rate=("conversion_flag", "mean"),
            average_sale_value=("final_sale_price", "mean"),
            fastest_response_hours=("fastest_response_hours", "mean"),
        )
        .reset_index()
        .sort_values("conversion_rate", ascending=False)
    )
    response_labels = [
        "<4 hours",
        "4-8 hours",
        "8-16 hours",
        "16-24 hours",
        "24+ hours",
    ]
    response = (
        inquiries.assign(
            response_band=pd.cut(
                inquiries["fastest_response_hours"],
                [-0.01, 4, 8, 16, 24, np.inf],
                labels=response_labels,
                right=False,
            )
        )
        .groupby("response_band", observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversion_rate=("conversion_flag", "mean"),
            average_sale_value=("final_sale_price", "mean"),
        )
        .reindex(response_labels)
        .reset_index()
    )
    age_labels = ["0-2 years", "3-5 years", "6-9 years", "10+ years"]
    age = (
        inquiries.assign(
            vehicle_age_band=pd.cut(
                inquiries["vehicle_age_at_inquiry"],
                [-1, 2, 5, 9, np.inf],
                labels=age_labels,
            )
        )
        .groupby("vehicle_age_band", observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversion_rate=("conversion_flag", "mean"),
            average_quote_spread=("quote_spread", "mean"),
            average_quote_spread_pct=("quote_spread_pct", "mean"),
        )
        .reindex(age_labels)
        .reset_index()
    )
    inquiry_vehicle = inquiries.merge(
        vehicles[
            [
                "vehicle_id",
                "brand",
                "model",
                "vehicle_type",
                "estimated_market_value",
                "mileage_bracket",
            ]
        ],
        on="vehicle_id",
        validate="one_to_one",
    )
    segments = (
        inquiry_vehicle.groupby("vehicle_type", observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversion_rate=("conversion_flag", "mean"),
            average_market_value=("estimated_market_value", "mean"),
            accepted_value=("final_sale_price", "sum"),
        )
        .reset_index()
        .sort_values("accepted_value", ascending=False)
    )
    brands = (
        inquiry_vehicle.groupby("brand", observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversion_rate=("conversion_flag", "mean"),
            average_market_value=("estimated_market_value", "mean"),
            average_sale_value=("final_sale_price", "mean"),
            accepted_value=("final_sale_price", "sum"),
        )
        .reset_index()
        .sort_values("accepted_value", ascending=False)
    )
    quote_dealer = quotes.merge(
        dealers[["dealer_id", "dealer_name", "dealer_region"]],
        on="dealer_id",
        validate="many_to_one",
    )
    dealer = (
        quote_dealer.groupby(
            ["dealer_id", "dealer_name", "dealer_region"], observed=True
        )
        .agg(
            quotes=("quote_id", "size"),
            wins=("accepted_flag", "sum"),
            win_rate=("accepted_flag", "mean"),
            average_response_hours=("response_time_hours", "mean"),
            average_quote_to_market_ratio=("quote_to_market_ratio", "mean"),
        )
        .reset_index()
    )
    accepted_by_dealer = (
        quote_dealer.loc[quote_dealer["accepted_flag"]]
        .groupby("dealer_id", observed=True)["quote_amount"]
        .sum()
    )
    dealer["accepted_value"] = dealer["dealer_id"].map(accepted_by_dealer).fillna(0)
    dealer = dealer.sort_values("win_rate", ascending=False)

    annual = (
        inquiries.assign(year=inquiries["inquiry_date"].dt.year)
        .groupby("year", observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversion_rate=("conversion_flag", "mean"),
            accepted_value=("final_sale_price", "sum"),
        )
        .reset_index()
    )
    response_by_year = (
        inquiries.assign(
            year=inquiries["inquiry_date"].dt.year,
            response_group=np.where(
                inquiries["fastest_response_hours"].lt(8), "Under 8 hours", "8+ hours"
            ),
        )
        .groupby(["year", "response_group"], observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversions=("conversion_flag", "sum"),
        )
        .reset_index()
    )
    response_by_year["conversion_rate"] = (
        response_by_year["conversions"] / response_by_year["inquiries"]
    )
    response_by_year["ci_95_low"], response_by_year["ci_95_high"] = _wilson_interval(
        response_by_year["conversions"], response_by_year["inquiries"]
    )
    response_stability = (
        response_by_year.pivot(
            index="year", columns="response_group", values="conversion_rate"
        )
        .rename_axis(columns=None)
        .reset_index()
    )
    response_stability["lift_percentage_points"] = (
        response_stability["Under 8 hours"] - response_stability["8+ hours"]
    ) * 100

    lead_by_year = (
        inquiries.loc[
            inquiries["lead_source"].isin(["Dealer Referral", "Social Media"])
        ]
        .assign(year=lambda frame: frame["inquiry_date"].dt.year)
        .groupby(["year", "lead_source"], observed=True)
        .agg(
            inquiries=("inquiry_id", "size"),
            conversions=("conversion_flag", "sum"),
            conversion_rate=("conversion_flag", "mean"),
        )
        .reset_index()
    )
    lead_stability = (
        lead_by_year.pivot(
            index="year", columns="lead_source", values="conversion_rate"
        )
        .rename_axis(columns=None)
        .reset_index()
    )
    lead_stability["referral_lift_percentage_points"] = (
        lead_stability["Dealer Referral"] - lead_stability["Social Media"]
    ) * 100
    accepted_quotes = quotes["accepted_flag"]
    processed_score = float(
        quality.loc[
            quality["stage"].eq("Processed")
            & quality["metric_name"].eq("overall_data_quality_score"),
            "rate",
        ].iloc[0]
    )
    raw_score = float(
        quality.loc[
            quality["stage"].eq("Raw")
            & quality["metric_name"].eq("overall_data_quality_score"),
            "rate",
        ].iloc[0]
    )
    under_8 = inquiries["fastest_response_hours"].lt(8)
    dealer_referral_rate = float(
        lead.loc[lead["lead_source"].eq("Dealer Referral"), "conversion_rate"].iloc[0]
    )
    social_rate = float(
        lead.loc[lead["lead_source"].eq("Social Media"), "conversion_rate"].iloc[0]
    )
    newest_spread_pct = float(
        age.loc[
            age["vehicle_age_band"].eq("0-2 years"), "average_quote_spread_pct"
        ].iloc[0]
    )
    oldest_spread_pct = float(
        age.loc[
            age["vehicle_age_band"].eq("10+ years"), "average_quote_spread_pct"
        ].iloc[0]
    )
    suv_value = float(
        segments.loc[segments["vehicle_type"].eq("Suv"), "accepted_value"].iloc[0]
    )

    return {
        "metadata": {
            "dataset_type": "Synthetic",
            "seed": 42,
            "start_date": str(inquiries["inquiry_date"].min().date()),
            "end_date": str(inquiries["inquiry_date"].max().date()),
            "currency": "CHF",
            "analysis_grain": "Inquiry for conversion; quote for dealer competitiveness",
        },
        "kpis": {
            "total_inquiries": int(len(inquiries)),
            "total_quotes": int(len(quotes)),
            "converted_inquiries": int(inquiries["conversion_flag"].sum()),
            "conversion_rate": float(inquiries["conversion_flag"].mean()),
            "average_sale_value": float(inquiries["final_sale_price"].mean()),
            "total_accepted_value": float(inquiries["final_sale_price"].sum()),
            "average_quote_spread": float(inquiries["quote_spread"].mean()),
            "average_quote_spread_pct": float(inquiries["quote_spread_pct"].mean()),
            "average_quote_response_hours": float(quotes["response_time_hours"].mean()),
            "average_fastest_response_hours": float(
                inquiries["fastest_response_hours"].mean()
            ),
            "average_quotes_per_inquiry": float(inquiries["quote_count"].mean()),
            "active_dealers": int(dealers["active_flag"].astype(bool).sum()),
            "quote_anomalies": int(quotes["anomaly_flag"].astype(bool).sum()),
            "quote_anomaly_rate": float(quotes["anomaly_flag"].astype(bool).mean()),
            "raw_data_quality_score": raw_score,
            "processed_data_quality_score": processed_score,
        },
        "evidence": {
            "inquiry_growth_2022_to_2025": float(
                annual.loc[annual["year"].eq(2025), "inquiries"].iloc[0]
                / annual.loc[annual["year"].eq(2022), "inquiries"].iloc[0]
                - 1
            ),
            "conversion_under_8_hours": float(
                inquiries.loc[under_8, "conversion_flag"].mean()
            ),
            "conversion_8_hours_or_more": float(
                inquiries.loc[~under_8, "conversion_flag"].mean()
            ),
            "dealer_referral_conversion_rate": dealer_referral_rate,
            "social_media_conversion_rate": social_rate,
            "dealer_referral_lift_pp_vs_social": (dealer_referral_rate - social_rate)
            * 100,
            "accepted_quote_ratio": float(
                quotes.loc[accepted_quotes, "quote_to_market_ratio"].mean()
            ),
            "nonaccepted_quote_ratio": float(
                quotes.loc[~accepted_quotes, "quote_to_market_ratio"].mean()
            ),
            "accepted_quote_response_hours": float(
                quotes.loc[accepted_quotes, "response_time_hours"].mean()
            ),
            "nonaccepted_quote_response_hours": float(
                quotes.loc[~accepted_quotes, "response_time_hours"].mean()
            ),
            "older_to_newer_relative_spread_ratio": oldest_spread_pct
            / newest_spread_pct,
            "suv_share_of_accepted_value": suv_value
            / float(inquiries["final_sale_price"].sum()),
            "dealer_win_rate_p10": float(dealer["win_rate"].quantile(0.10)),
            "dealer_win_rate_median": float(dealer["win_rate"].median()),
            "dealer_win_rate_p90": float(dealer["win_rate"].quantile(0.90)),
            "dealer_competitiveness_win_correlation": float(
                dealer["average_quote_to_market_ratio"].corr(dealer["win_rate"])
            ),
            "dealer_response_win_correlation": float(
                dealer["average_response_hours"].corr(dealer["win_rate"])
            ),
            "response_lift_pp_min_year": float(
                response_stability["lift_percentage_points"].min()
            ),
            "response_lift_pp_max_year": float(
                response_stability["lift_percentage_points"].max()
            ),
            "referral_lift_pp_min_year": float(
                lead_stability["referral_lift_percentage_points"].min()
            ),
            "referral_lift_pp_max_year": float(
                lead_stability["referral_lift_percentage_points"].max()
            ),
        },
        "monthly": _records(monthly),
        "annual": _records(annual),
        "response_by_year": _records(response_by_year),
        "response_stability": _records(response_stability),
        "lead_source_by_year": _records(lead_by_year),
        "lead_source_stability": _records(lead_stability),
        "lead_sources": _records(lead),
        "response_bands": _records(response),
        "vehicle_age_bands": _records(age),
        "vehicle_segments": _records(segments),
        "top_brands": _records(brands.head(10)),
        "top_dealers": _records(dealer.head(15)),
        "dealer_detail": _records(dealer),
        "quality_metrics": _records(quality),
        "quality_issues": _records(tables["issues"]),
    }


def save_analysis_summary(
    summary: dict[str, Any], processed_dir: Path = PROCESSED_DIR
) -> None:
    """Persist exact evidence in JSON plus a compact KPI CSV."""

    json_path = processed_dir / "analysis_summary.json"
    temporary_path = json_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary_path.replace(json_path)
    kpi_frame = pd.DataFrame(
        {"metric_name": list(summary["kpis"]), "value": list(summary["kpis"].values())}
    )
    write_csv(kpi_frame, processed_dir / "analysis_kpis.csv")


def build_analysis_artifacts(
    processed_dir: Path = PROCESSED_DIR,
) -> dict[str, Any]:
    """Build persisted KPI evidence from the curated data."""

    ensure_project_directories()
    tables = load_curated_data(processed_dir)
    summary = calculate_analysis_summary(tables)
    save_analysis_summary(summary, processed_dir)
    LOGGER.info("Wrote analysis summary and KPI evidence")
    return summary


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    build_analysis_artifacts()


if __name__ == "__main__":
    main()

