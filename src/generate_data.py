"""Generate a reproducible Swiss automotive marketplace dataset with raw defects."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    RAW_DIR,
    REFERENCE_DIR,
    GeneratorConfig,
    ensure_project_directories,
)
from .utils import configure_logging, write_csv


LOGGER = configure_logging()

CANTON_REGION = {
    "ZH": "Zurich",
    "BE": "Espace Mittelland",
    "LU": "Central Switzerland",
    "UR": "Central Switzerland",
    "SZ": "Central Switzerland",
    "OW": "Central Switzerland",
    "NW": "Central Switzerland",
    "GL": "Eastern Switzerland",
    "ZG": "Central Switzerland",
    "FR": "Espace Mittelland",
    "SO": "Espace Mittelland",
    "BS": "Northwestern Switzerland",
    "BL": "Northwestern Switzerland",
    "SH": "Eastern Switzerland",
    "AR": "Eastern Switzerland",
    "AI": "Eastern Switzerland",
    "SG": "Eastern Switzerland",
    "GR": "Eastern Switzerland",
    "AG": "Northwestern Switzerland",
    "TG": "Eastern Switzerland",
    "TI": "Ticino",
    "VD": "Lake Geneva",
    "VS": "Lake Geneva",
    "NE": "Espace Mittelland",
    "GE": "Lake Geneva",
    "JU": "Espace Mittelland",
}

CANTON_WEIGHTS = np.array(
    [
        0.185,
        0.125,
        0.050,
        0.004,
        0.020,
        0.004,
        0.005,
        0.015,
        0.036,
        0.038,
        0.033,
        0.024,
        0.032,
        0.010,
        0.006,
        0.002,
        0.064,
        0.024,
        0.080,
        0.035,
        0.043,
        0.097,
        0.041,
        0.022,
        0.061,
        0.014,
    ]
)
CANTON_WEIGHTS = CANTON_WEIGHTS / CANTON_WEIGHTS.sum()

LEAD_SOURCES = np.array(
    [
        "Organic Search",
        "Paid Search",
        "Dealer Referral",
        "Social Media",
        "Direct",
        "Partner",
    ]
)
LEAD_SOURCE_WEIGHTS = np.array([0.27, 0.19, 0.16, 0.12, 0.18, 0.08])


def _vehicle_catalog() -> pd.DataFrame:
    """Return a compact European vehicle reference catalog."""

    rows = [
        ("Volkswagen", "Golf", "Hatchback", 36_000, 0.090),
        ("Volkswagen", "Tiguan", "SUV", 49_000, 0.070),
        ("Volkswagen", "Passat", "Estate", 47_000, 0.030),
        ("BMW", "3 Series", "Sedan", 59_000, 0.050),
        ("BMW", "X3", "SUV", 72_000, 0.045),
        ("BMW", "1 Series", "Hatchback", 45_000, 0.025),
        ("Mercedes-Benz", "C-Class", "Sedan", 63_000, 0.045),
        ("Mercedes-Benz", "GLC", "SUV", 76_000, 0.040),
        ("Mercedes-Benz", "A-Class", "Hatchback", 46_000, 0.025),
        ("Audi", "A3", "Hatchback", 47_000, 0.040),
        ("Audi", "A4", "Estate", 59_000, 0.035),
        ("Audi", "Q5", "SUV", 71_000, 0.040),
        ("Skoda", "Octavia", "Estate", 39_000, 0.060),
        ("Skoda", "Kodiaq", "SUV", 48_000, 0.035),
        ("Toyota", "Corolla", "Hatchback", 34_000, 0.045),
        ("Toyota", "RAV4", "SUV", 47_000, 0.040),
        ("Tesla", "Model 3", "Sedan", 49_000, 0.040),
        ("Tesla", "Model Y", "SUV", 55_000, 0.045),
        ("Renault", "Clio", "Hatchback", 25_000, 0.035),
        ("Renault", "Captur", "SUV", 31_000, 0.025),
        ("Peugeot", "208", "Hatchback", 27_000, 0.030),
        ("Peugeot", "3008", "SUV", 40_000, 0.025),
        ("Ford", "Focus", "Hatchback", 31_000, 0.030),
        ("Ford", "Kuga", "SUV", 42_000, 0.025),
        ("Volvo", "XC40", "SUV", 54_000, 0.025),
        ("Volvo", "XC60", "SUV", 69_000, 0.020),
        ("Porsche", "Macan", "SUV", 98_000, 0.012),
        ("Porsche", "911", "Sports", 155_000, 0.005),
        ("Fiat", "500", "Hatchback", 24_000, 0.025),
        ("Hyundai", "Tucson", "SUV", 42_000, 0.025),
        ("Hyundai", "i30", "Hatchback", 30_000, 0.020),
        ("Kia", "Sportage", "SUV", 41_000, 0.020),
        ("Dacia", "Duster", "SUV", 27_000, 0.017),
        ("Opel", "Astra", "Hatchback", 31_000, 0.020),
        ("Mazda", "CX-5", "SUV", 44_000, 0.018),
        ("Land Rover", "Range Rover Evoque", "SUV", 67_000, 0.010),
        ("Nissan", "Qashqai", "SUV", 39_000, 0.018),
        ("Citroen", "C3", "Hatchback", 25_000, 0.015),
        ("SEAT", "Leon", "Hatchback", 32_000, 0.020),
        ("Cupra", "Formentor", "SUV", 46_000, 0.020),
        ("Iveco", "Daily", "Van", 57_000, 0.010),
        ("Volkswagen", "Transporter", "Van", 55_000, 0.020),
    ]
    catalog = pd.DataFrame(
        rows, columns=["brand", "model", "vehicle_type", "base_new_price", "weight"]
    )
    catalog["weight"] = catalog["weight"] / catalog["weight"].sum()
    return catalog


def _sample_inquiry_dates(
    rng: np.random.Generator, count: int, start_date: str, end_date: str
) -> pd.DatetimeIndex:
    """Sample dates with annual growth and Swiss-market seasonality."""

    possible_dates = pd.date_range(start_date, end_date, freq="D")
    month_factor = {
        1: 0.86,
        2: 0.91,
        3: 1.08,
        4: 1.12,
        5: 1.10,
        6: 1.05,
        7: 0.94,
        8: 0.98,
        9: 1.09,
        10: 1.10,
        11: 0.96,
        12: 0.78,
    }
    year_factor = {2022: 0.86, 2023: 0.95, 2024: 1.04, 2025: 1.14}
    weights = np.array(
        [
            month_factor[value.month] * year_factor[value.year]
            for value in possible_dates
        ]
    )
    weights = weights / weights.sum()
    sampled = possible_dates[rng.choice(len(possible_dates), size=count, p=weights)]
    return pd.DatetimeIndex(sampled)


def _make_customers(
    rng: np.random.Generator,
    config: GeneratorConfig,
    inquiry_customer_numbers: np.ndarray,
    inquiry_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Create customer profiles whose registration predates their first inquiry."""

    customer_numbers = np.arange(1, config.customer_count + 1)
    customer_ids = np.array([f"C{value:06d}" for value in customer_numbers])
    first_inquiry = (
        pd.DataFrame(
            {
                "customer_number": inquiry_customer_numbers,
                "inquiry_date": inquiry_dates,
            }
        )
        .groupby("customer_number", observed=True)["inquiry_date"]
        .min()
    )
    reference_dates = pd.Series(customer_numbers).map(first_inquiry)
    fallback_dates = pd.to_datetime("2025-12-27") - pd.to_timedelta(
        rng.integers(0, 1_200, size=config.customer_count), unit="D"
    )
    reference_dates = pd.to_datetime(reference_dates).fillna(pd.Series(fallback_dates))
    created_dates = reference_dates - pd.to_timedelta(
        rng.integers(1, 900, size=config.customer_count), unit="D"
    )
    created_dates = created_dates.clip(lower=pd.Timestamp("2018-01-01"))

    cantons = np.array(list(CANTON_REGION))
    return pd.DataFrame(
        {
            "customer_id": customer_ids,
            "customer_created_date": created_dates.dt.date,
            "age_group": rng.choice(
                ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"],
                size=config.customer_count,
                p=[0.08, 0.24, 0.24, 0.20, 0.15, 0.09],
            ),
            "canton": rng.choice(cantons, size=config.customer_count, p=CANTON_WEIGHTS),
            "customer_type": rng.choice(
                ["Private", "Business", "Fleet"],
                size=config.customer_count,
                p=[0.79, 0.16, 0.05],
            ),
            "preferred_contact_method": rng.choice(
                ["Email", "Phone", "SMS", "WhatsApp"],
                size=config.customer_count,
                p=[0.39, 0.28, 0.13, 0.20],
            ),
            "lead_source": rng.choice(
                LEAD_SOURCES,
                size=config.customer_count,
                p=LEAD_SOURCE_WEIGHTS,
            ),
        }
    )


def _make_dealers(
    rng: np.random.Generator, config: GeneratorConfig
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Create dealers plus hidden behavioral factors used by the generator."""

    regions = np.array(sorted(set(CANTON_REGION.values())))
    dealer_numbers = np.arange(1, config.dealer_count + 1)
    dealer_region = rng.choice(
        regions,
        size=config.dealer_count,
        p=np.array([0.19, 0.14, 0.12, 0.19, 0.08, 0.13, 0.15]),
    )
    dealer_type = rng.choice(
        ["Franchise", "Independent", "Online Specialist"],
        size=config.dealer_count,
        p=[0.50, 0.37, 0.13],
    )
    rating = np.clip(rng.normal(4.15, 0.42, config.dealer_count), 2.7, 5.0)
    dealers = pd.DataFrame(
        {
            "dealer_id": [f"D{value:04d}" for value in dealer_numbers],
            "dealer_name": [
                f"{region.split()[0]} Autohaus {value:03d}"
                for value, region in zip(dealer_numbers, dealer_region)
            ],
            "dealer_region": dealer_region,
            "dealer_type": dealer_type,
            "dealer_rating": np.round(rating, 2),
            "active_flag": rng.choice(
                [True, False], size=config.dealer_count, p=[0.92, 0.08]
            ),
        }
    )
    competitiveness = np.clip(
        0.92 + (rating - 4.0) * 0.018 + rng.normal(0, 0.025, config.dealer_count),
        0.84,
        1.02,
    )
    speed_factor = np.clip(
        np.exp(rng.normal(-0.10 - (rating - 4.0) * 0.08, 0.30, config.dealer_count)),
        0.45,
        2.10,
    )
    return dealers, competitiveness, speed_factor


def _make_vehicles(
    rng: np.random.Generator,
    inquiry_dates: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Create one appraised vehicle per inquiry with economic relationships."""

    count = len(inquiry_dates)
    catalog = _vehicle_catalog()
    catalog_index = rng.choice(len(catalog), size=count, p=catalog["weight"])
    selected = catalog.iloc[catalog_index].reset_index(drop=True)
    inquiry_year = inquiry_dates.year.to_numpy()
    age = np.clip(rng.gamma(shape=2.1, scale=2.7, size=count).astype(int), 0, 18)
    manufacture_year = inquiry_year - age

    annual_mileage = np.clip(rng.normal(14_500, 5_500, count), 2_000, 40_000)
    mileage = np.maximum(
        0,
        annual_mileage * age + rng.normal(4_000, 7_000, count),
    ).astype(int)
    mileage = np.minimum(mileage, 420_000)

    random_fuel = rng.random(count)
    ev_probability = np.clip(0.015 + (manufacture_year - 2012) * 0.023, 0.01, 0.32)
    tesla_mask = selected["brand"].eq("Tesla").to_numpy()
    ev_probability[tesla_mask] = 0.94
    hybrid_probability = np.clip(0.05 + (manufacture_year - 2014) * 0.012, 0.03, 0.18)
    diesel_probability = np.where(
        selected["vehicle_type"].isin(["SUV", "Estate", "Van"]), 0.31, 0.20
    )
    fuel_type = np.full(count, "Petrol", dtype=object)
    fuel_type[random_fuel < diesel_probability] = "Diesel"
    fuel_type[random_fuel < hybrid_probability] = "Hybrid"
    fuel_type[random_fuel < ev_probability] = "Electric"

    condition_score = 3.4 - age * 0.11 - mileage / 180_000 + rng.normal(0, 0.45, count)
    condition = np.select(
        [condition_score >= 3.1, condition_score >= 2.2, condition_score >= 1.3],
        ["Excellent", "Good", "Fair"],
        default="Poor",
    )
    condition_factor = pd.Series(condition).map(
        {"Excellent": 1.08, "Good": 1.00, "Fair": 0.89, "Poor": 0.73}
    )
    depreciation = np.power(0.875, age)
    mileage_factor = np.exp(-mileage / 310_000)
    market_value = (
        selected["base_new_price"].to_numpy()
        * depreciation
        * mileage_factor
        * condition_factor.to_numpy()
        * rng.lognormal(mean=0.0, sigma=0.055, size=count)
    )
    market_value = np.clip(market_value, 1_200, 220_000)

    vehicles = pd.DataFrame(
        {
            "vehicle_id": [f"V{value:07d}" for value in range(1, count + 1)],
            "brand": selected["brand"],
            "model": selected["model"],
            "vehicle_type": selected["vehicle_type"],
            "fuel_type": fuel_type,
            "manufacture_year": manufacture_year,
            "mileage_km": mileage,
            "estimated_market_value": np.round(market_value, 2),
            "vehicle_condition": condition,
        }
    )
    return vehicles, age


def _make_inquiries_and_quotes(
    rng: np.random.Generator,
    config: GeneratorConfig,
    inquiry_dates: pd.DatetimeIndex,
    inquiry_customer_numbers: np.ndarray,
    customers: pd.DataFrame,
    vehicles: pd.DataFrame,
    vehicle_age: np.ndarray,
    dealers: pd.DataFrame,
    dealer_competitiveness: np.ndarray,
    dealer_speed_factor: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate linked inquiries and competing quotes with conversion behavior."""

    inquiry_count = config.inquiry_count
    inquiry_ids = np.array([f"I{value:07d}" for value in range(1, inquiry_count + 1)])
    customer_index = inquiry_customer_numbers - 1
    primary_sources = customers["lead_source"].to_numpy()[customer_index]
    inquiry_sources = np.where(
        rng.random(inquiry_count) < 0.72,
        primary_sources,
        rng.choice(LEAD_SOURCES, size=inquiry_count, p=LEAD_SOURCE_WEIGHTS),
    )

    quote_counts = rng.choice(
        [2, 3, 4, 5], size=inquiry_count, p=[0.15, 0.40, 0.30, 0.15]
    )
    inquiry_position = np.repeat(np.arange(inquiry_count), quote_counts)
    group_starts = np.repeat(np.cumsum(quote_counts) - quote_counts, quote_counts)
    quote_position = np.arange(len(inquiry_position)) - group_starts

    dealer_base = rng.integers(0, config.dealer_count, size=inquiry_count)
    dealer_index = (
        dealer_base[inquiry_position] + quote_position * 31
    ) % config.dealer_count
    quote_dealer_ids = dealers["dealer_id"].to_numpy()[dealer_index]

    market_value = vehicles["estimated_market_value"].to_numpy()[inquiry_position]
    dispersion_sigma = 0.021 + vehicle_age[inquiry_position] * 0.0042
    quote_ratio = dealer_competitiveness[dealer_index] * (
        1 + rng.normal(0, dispersion_sigma)
    )
    quote_ratio = np.clip(quote_ratio, 0.55, 1.16)
    quote_amount = np.round(market_value * quote_ratio, 2)

    inquiry_canton = customers["canton"].to_numpy()[customer_index]
    inquiry_region = np.array([CANTON_REGION[value] for value in inquiry_canton])
    quote_region = inquiry_region[inquiry_position]
    dealer_region = dealers["dealer_region"].to_numpy()[dealer_index]
    regional_speed = np.where(quote_region == dealer_region, 0.88, 1.08)
    response_time = (
        rng.lognormal(mean=np.log(10.5), sigma=0.62, size=len(inquiry_position))
        * dealer_speed_factor[dealer_index]
        * regional_speed
    )
    response_time = np.round(np.clip(response_time, 0.35, 96.0), 2)
    response_days = np.floor(response_time / 24).astype("timedelta64[D]")
    quote_dates = (
        inquiry_dates.to_numpy(dtype="datetime64[D]")[inquiry_position] + response_days
    )

    dealer_rating = dealers["dealer_rating"].to_numpy()[dealer_index]
    utility = (
        quote_ratio * 3.6
        - np.log1p(response_time) * 0.075
        + dealer_rating * 0.025
        + rng.normal(0, 0.025, len(inquiry_position))
    )

    quotes = pd.DataFrame(
        {
            "quote_id": [
                f"Q{value:08d}" for value in range(1, len(inquiry_position) + 1)
            ],
            "inquiry_id": inquiry_ids[inquiry_position],
            "dealer_id": quote_dealer_ids,
            "quote_date": pd.to_datetime(quote_dates).date,
            "quote_amount": quote_amount,
            "response_time_hours": response_time,
            "quote_rank": 0,
            "accepted_flag": False,
            "_utility": utility,
        }
    )
    quotes["quote_rank"] = (
        quotes.groupby("inquiry_id", observed=True)["quote_amount"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    quote_summary = quotes.groupby("inquiry_id", observed=True).agg(
        highest_quote=("quote_amount", "max"),
        lowest_quote=("quote_amount", "min"),
        fastest_response=("response_time_hours", "min"),
    )
    best_ratio = (
        quote_summary["highest_quote"].to_numpy()
        / vehicles["estimated_market_value"].to_numpy()
    )
    lead_effect = (
        pd.Series(inquiry_sources)
        .map(
            {
                "Dealer Referral": 0.36,
                "Partner": 0.23,
                "Direct": 0.16,
                "Organic Search": 0.09,
                "Paid Search": -0.12,
                "Social Media": -0.19,
            }
        )
        .to_numpy()
    )
    segment_effect = (
        vehicles["vehicle_type"]
        .map(
            {
                "SUV": 0.10,
                "Estate": 0.07,
                "Sedan": 0.03,
                "Hatchback": 0.00,
                "Van": -0.05,
                "Sports": -0.12,
            }
        )
        .to_numpy()
    )
    seasonal_effect = np.where(
        np.isin(inquiry_dates.month, [3, 4, 5, 9, 10]), 0.10, -0.04
    )
    logit = (
        -1.18
        + 2.5 * (best_ratio - 0.90)
        - 0.020 * (quote_summary["fastest_response"].to_numpy() - 10)
        + lead_effect
        + segment_effect
        + seasonal_effect
        + 0.07 * (quote_counts - 3)
    )
    conversion_probability = 1 / (1 + np.exp(-logit))
    conversion_flag = rng.random(inquiry_count) < conversion_probability

    winner_indices = (
        quotes.groupby("inquiry_id", observed=True)["_utility"].idxmax().to_numpy()
    )
    converted_winner_indices = winner_indices[conversion_flag]
    quotes.loc[converted_winner_indices, "accepted_flag"] = True

    winning_dealer_id = np.full(inquiry_count, None, dtype=object)
    final_sale_price = np.full(inquiry_count, np.nan)
    winning_dealer_id[conversion_flag] = quotes.loc[
        converted_winner_indices, "dealer_id"
    ].to_numpy()
    final_sale_price[conversion_flag] = quotes.loc[
        converted_winner_indices, "quote_amount"
    ].to_numpy()
    days_to_conversion = np.full(inquiry_count, np.nan)
    conversion_delay = np.ceil(
        quotes.loc[converted_winner_indices, "response_time_hours"].to_numpy() / 24
        + rng.gamma(1.8, 1.1, conversion_flag.sum())
    )
    days_to_conversion[conversion_flag] = np.clip(conversion_delay, 1, 21)

    non_converted_status = rng.choice(
        ["Lost", "Expired", "Open"],
        size=inquiry_count,
        p=[0.55, 0.39, 0.06],
    )
    status = np.where(conversion_flag, "Converted", non_converted_status)
    inquiries = pd.DataFrame(
        {
            "inquiry_id": inquiry_ids,
            "customer_id": [f"C{value:06d}" for value in inquiry_customer_numbers],
            "vehicle_id": [f"V{value:07d}" for value in range(1, inquiry_count + 1)],
            "inquiry_date": inquiry_dates.date,
            "lead_source": inquiry_sources,
            "status": status,
            "final_sale_price": np.round(final_sale_price, 2),
            "winning_dealer_id": winning_dealer_id,
            "conversion_flag": conversion_flag,
            "days_to_conversion": days_to_conversion,
        }
    )
    return inquiries, quotes.drop(columns="_utility")


def _inject_raw_issues(
    rng: np.random.Generator, tables: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    """Introduce deterministic, documented defects only in the raw layer."""

    raw = {name: frame.copy() for name, frame in tables.items()}

    customers = raw["dim_customer"]
    missing_index = rng.choice(
        customers.index, size=max(1, len(customers) // 250), replace=False
    )
    customers.loc[missing_index, "canton"] = pd.NA
    messy_index = rng.choice(
        customers.index, size=max(1, len(customers) // 300), replace=False
    )
    customers.loc[messy_index, "lead_source"] = (
        "  " + customers.loc[messy_index, "lead_source"].str.lower() + " "
    )
    raw["dim_customer"] = pd.concat(
        [customers, customers.sample(frac=0.001, random_state=11)], ignore_index=True
    )

    vehicles = raw["dim_vehicle"]
    invalid_mileage_index = rng.choice(
        vehicles.index, size=max(2, len(vehicles) // 650), replace=False
    )
    half = len(invalid_mileage_index) // 2
    vehicles.loc[invalid_mileage_index[:half], "mileage_km"] = -5_000
    vehicles.loc[invalid_mileage_index[half:], "mileage_km"] = 900_000
    missing_fuel_index = rng.choice(
        vehicles.index, size=max(1, len(vehicles) // 300), replace=False
    )
    vehicles.loc[missing_fuel_index, "fuel_type"] = pd.NA
    messy_brand_index = rng.choice(
        vehicles.index, size=max(1, len(vehicles) // 500), replace=False
    )
    vehicles.loc[messy_brand_index, "brand"] = (
        " " + vehicles.loc[messy_brand_index, "brand"].str.upper() + "  "
    )
    raw["dim_vehicle"] = vehicles

    dealers = raw["dim_dealer"]
    messy_dealer_index = rng.choice(
        dealers.index, size=max(1, len(dealers) // 30), replace=False
    )
    dealers.loc[messy_dealer_index, "dealer_name"] = (
        "  " + dealers.loc[messy_dealer_index, "dealer_name"] + " "
    )
    raw["dim_dealer"] = pd.concat(
        [dealers, dealers.sample(n=2, random_state=12)], ignore_index=True
    )

    inquiries = raw["fact_inquiry"]
    malformed_date_index = rng.choice(
        inquiries.index, size=max(1, len(inquiries) // 900), replace=False
    )
    inquiries["inquiry_date"] = inquiries["inquiry_date"].astype(str)
    inquiries.loc[malformed_date_index, "inquiry_date"] = "2025-99-41"
    converted_indices = inquiries.index[inquiries["conversion_flag"].astype(bool)]
    bad_winner_index = rng.choice(
        converted_indices, size=max(1, len(inquiries) // 2_000), replace=False
    )
    inquiries.loc[bad_winner_index, "winning_dealer_id"] = "D9999"
    messy_status_index = rng.choice(
        inquiries.index, size=max(1, len(inquiries) // 700), replace=False
    )
    inquiries.loc[messy_status_index, "status"] = (
        " " + inquiries.loc[messy_status_index, "status"].str.lower() + " "
    )
    raw["fact_inquiry"] = pd.concat(
        [inquiries, inquiries.sample(frac=0.0015, random_state=13)], ignore_index=True
    )

    quotes = raw["fact_quote"]
    quote_count = len(quotes)
    impossible_index = rng.choice(
        quotes.index, size=max(2, quote_count // 700), replace=False
    )
    half = len(impossible_index) // 2
    quotes.loc[impossible_index[:half], "quote_amount"] = -1
    quotes.loc[impossible_index[half:], "quote_amount"] = 9_999_999
    orphan_index = rng.choice(
        quotes.index.difference(impossible_index),
        size=max(1, quote_count // 1_000),
        replace=False,
    )
    quotes.loc[orphan_index, "dealer_id"] = "D9999"
    missing_response_index = rng.choice(
        quotes.index, size=max(1, quote_count // 500), replace=False
    )
    quotes.loc[missing_response_index, "response_time_hours"] = np.nan
    malformed_quote_date_index = rng.choice(
        quotes.index, size=max(1, quote_count // 1_200), replace=False
    )
    quotes["quote_date"] = quotes["quote_date"].astype(str)
    quotes.loc[malformed_quote_date_index, "quote_date"] = "not-a-date"
    raw["fact_quote"] = pd.concat(
        [quotes, quotes.sample(frac=0.0015, random_state=14)], ignore_index=True
    )
    return raw


def generate_dataset(
    config: GeneratorConfig = GeneratorConfig(),
    raw_dir: Path = RAW_DIR,
    reference_dir: Path = REFERENCE_DIR,
) -> dict[str, int]:
    """Generate all raw and reference CSVs and return row counts."""

    ensure_project_directories()
    rng = np.random.default_rng(config.seed)
    LOGGER.info(
        "Generating dataset seed=%s customers=%s inquiries=%s dealers=%s",
        config.seed,
        f"{config.customer_count:,}",
        f"{config.inquiry_count:,}",
        f"{config.dealer_count:,}",
    )

    inquiry_dates = _sample_inquiry_dates(
        rng, config.inquiry_count, config.start_date, config.end_date
    )
    inquiry_customer_numbers = rng.integers(
        1, config.customer_count + 1, size=config.inquiry_count
    )
    customers = _make_customers(rng, config, inquiry_customer_numbers, inquiry_dates)
    dealers, dealer_competitiveness, dealer_speed_factor = _make_dealers(rng, config)
    vehicles, vehicle_age = _make_vehicles(rng, inquiry_dates)
    inquiries, quotes = _make_inquiries_and_quotes(
        rng,
        config,
        inquiry_dates,
        inquiry_customer_numbers,
        customers,
        vehicles,
        vehicle_age,
        dealers,
        dealer_competitiveness,
        dealer_speed_factor,
    )

    dim_date = pd.DataFrame(
        {"date": pd.date_range(config.start_date, "2025-12-31", freq="D")}
    )
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["quarter"] = "Q" + dim_date["date"].dt.quarter.astype(str)
    dim_date["month"] = dim_date["date"].dt.month
    dim_date["month_name"] = dim_date["date"].dt.month_name()
    dim_date["week"] = dim_date["date"].dt.isocalendar().week.astype(int)
    dim_date["day_of_week"] = dim_date["date"].dt.day_name()
    dim_date["is_weekend"] = dim_date["date"].dt.dayofweek.ge(5)
    dim_date["date"] = dim_date["date"].dt.date

    clean_tables = {
        "dim_customer": customers,
        "dim_vehicle": vehicles,
        "dim_dealer": dealers,
        "fact_inquiry": inquiries,
        "fact_quote": quotes,
        "dim_date": dim_date,
    }
    raw_tables = _inject_raw_issues(rng, clean_tables)
    for table_name, frame in raw_tables.items():
        write_csv(frame, raw_dir / f"{table_name}.csv")
        LOGGER.info("Wrote raw %-16s %9s rows", table_name, f"{len(frame):,}")

    write_csv(_vehicle_catalog(), reference_dir / "vehicle_catalog.csv")
    write_csv(
        pd.DataFrame(
            {
                "canton": list(CANTON_REGION),
                "dealer_region": list(CANTON_REGION.values()),
            }
        ),
        reference_dir / "canton_regions.csv",
    )
    return {name: len(frame) for name, frame in raw_tables.items()}


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale customers and inquiries for a fast development run (default: 1.0).",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0 < args.scale <= 1:
        raise ValueError("--scale must be greater than 0 and no more than 1")
    base = GeneratorConfig(seed=args.seed)
    config = replace(
        base,
        customer_count=max(500, int(base.customer_count * args.scale)),
        inquiry_count=max(1_000, int(base.inquiry_count * args.scale)),
    )
    counts = generate_dataset(config)
    LOGGER.info("Generation complete: %s", counts)


if __name__ == "__main__":
    main()
