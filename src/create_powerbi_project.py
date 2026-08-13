"""Generate a source-controlled Power BI Project (PBIP) with TMDL and PBIR."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT
from .utils import configure_logging


LOGGER = configure_logging()
POWERBI_ROOT = PROJECT_ROOT / "powerbi"
PROJECT_NAME = "AutomotiveCommercialAnalytics"
PBIP_PATH = POWERBI_ROOT / f"{PROJECT_NAME}.pbip"
REPORT_DIR = POWERBI_ROOT / f"{PROJECT_NAME}.Report"
MODEL_DIR = POWERBI_ROOT / f"{PROJECT_NAME}.SemanticModel"

REPORT_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
)


TABLES: dict[str, dict[str, Any]] = {
    "Dim Date": {
        "source": "dim_date",
        "category": "Time",
        "columns": {
            "date": ("dateTime", False),
            "year": ("int64", False),
            "quarter": ("string", False),
            "month": ("int64", False),
            "month_name": ("string", False),
            "week": ("int64", False),
            "day_of_week": ("string", False),
            "is_weekend": ("boolean", False),
        },
    },
    "Dim Customer": {
        "source": "dim_customer",
        "columns": {
            "customer_id": ("string", True),
            "customer_created_date": ("dateTime", False),
            "age_group": ("string", False),
            "canton": ("string", False),
            "customer_type": ("string", False),
            "preferred_contact_method": ("string", False),
            "lead_source": ("string", False),
        },
    },
    "Dim Vehicle": {
        "source": "dim_vehicle",
        "columns": {
            "vehicle_id": ("string", True),
            "brand": ("string", False),
            "model": ("string", False),
            "vehicle_type": ("string", False),
            "fuel_type": ("string", False),
            "manufacture_year": ("int64", False),
            "mileage_km": ("int64", False),
            "estimated_market_value": ("decimal", False),
            "vehicle_condition": ("string", False),
            "mileage_bracket": ("string", False),
            "market_value_band": ("string", False),
        },
    },
    "Dim Dealer": {
        "source": "dim_dealer",
        "columns": {
            "dealer_id": ("string", True),
            "dealer_name": ("string", False),
            "dealer_region": ("string", False),
            "dealer_type": ("string", False),
            "dealer_rating": ("double", False),
            "active_flag": ("boolean", False),
        },
    },
    "Fact Inquiry": {
        "source": "fact_inquiry",
        "columns": {
            "inquiry_id": ("string", True),
            "customer_id": ("string", True),
            "vehicle_id": ("string", True),
            "inquiry_date": ("dateTime", False),
            "lead_source": ("string", False),
            "status": ("string", False),
            "final_sale_price": ("decimal", False),
            "winning_dealer_id": ("string", True),
            "conversion_flag": ("boolean", False),
            "days_to_conversion": ("int64", False),
            "quote_count": ("int64", False),
            "highest_quote": ("decimal", False),
            "lowest_quote": ("decimal", False),
            "average_quote": ("decimal", False),
            "fastest_response_hours": ("double", False),
            "quote_spread": ("decimal", False),
            "quote_spread_pct": ("double", False),
            "vehicle_age_at_inquiry": ("int64", False),
        },
    },
    "Fact Quote": {
        "source": "fact_quote",
        "columns": {
            "quote_id": ("string", True),
            "inquiry_id": ("string", True),
            "dealer_id": ("string", True),
            "quote_date": ("dateTime", False),
            "quote_amount": ("decimal", False),
            "response_time_hours": ("double", False),
            "quote_rank": ("int64", False),
            "accepted_flag": ("boolean", False),
            "estimated_market_value": ("decimal", False),
            "quote_to_market_ratio": ("double", False),
            "anomaly_flag": ("boolean", False),
        },
    },
    "Data Quality Metrics": {
        "source": "data_quality_metrics",
        "columns": {
            "metric_name": ("string", False),
            "stage": ("string", False),
            "passed_records": ("int64", False),
            "total_records": ("int64", False),
            "rate": ("double", False),
            "description": ("string", False),
            "assessment_date": ("dateTime", False),
        },
    },
    "Data Quality Issue Log": {
        "source": "data_quality_issue_log",
        "columns": {
            "issue_id": ("string", True),
            "table_name": ("string", False),
            "issue_type": ("string", False),
            "affected_rows": ("int64", False),
            "action": ("string", False),
            "final_result": ("string", False),
        },
    },
    "Pipeline Run Summary": {
        "source": "pipeline_run_summary",
        "columns": {
            "table_name": ("string", False),
            "raw_records": ("int64", False),
            "duplicate_records": ("int64", False),
            "corrected_records": ("int64", False),
            "quarantined_records": ("int64", False),
            "clean_records": ("int64", False),
            "loaded_records": ("int64", False),
            "load_status": ("string", False),
        },
    },
}


# Calculated columns are limited to fields that make a requested visual truthful at
# the intended grain. They do not replace any imported PostgreSQL column.
CALCULATED_COLUMNS: dict[str, dict[str, dict[str, Any]]] = {
    "Dim Date": {
        "Month Start": {
            "data_type": "dateTime",
            "expression": "DATE ( 'Dim Date'[year], 'Dim Date'[month], 1 )",
            "format_string": "MMM yyyy",
            "hidden": False,
        }
    },
    "Fact Inquiry": {
        "Response Time Band": {
            "data_type": "string",
            "expression": (
                "SWITCH ( TRUE (), 'Fact Inquiry'[fastest_response_hours] < 2, "
                '"Under 2 hours", \'Fact Inquiry\'[fastest_response_hours] < 4, '
                '"2-4 hours", \'Fact Inquiry\'[fastest_response_hours] < 8, '
                '"4-8 hours", \'Fact Inquiry\'[fastest_response_hours] < 12, '
                '"8-12 hours", "12+ hours" )'
            ),
            "format_string": None,
            "hidden": False,
            "sort_by": "Response Time Band Sort",
        },
        "Response Time Band Sort": {
            "data_type": "int64",
            "expression": (
                "SWITCH ( TRUE (), 'Fact Inquiry'[fastest_response_hours] < 2, 1, "
                "'Fact Inquiry'[fastest_response_hours] < 4, 2, "
                "'Fact Inquiry'[fastest_response_hours] < 8, 3, "
                "'Fact Inquiry'[fastest_response_hours] < 12, 4, 5 )"
            ),
            "format_string": "0",
            "hidden": True,
        },
    },
    "Data Quality Metrics": {
        "Metric Label": {
            "data_type": "string",
            "expression": (
                "SWITCH ( 'Data Quality Metrics'[metric_name], "
                '"completeness_rate", "Completeness", '
                '"overall_data_quality_score", "Overall quality score", '
                '"referential_integrity_rate", "Referential integrity", '
                '"uniqueness_rate", "Uniqueness", '
                '"validity_rate", "Validity", "Other" )'
            ),
            "format_string": None,
            "hidden": False,
        }
    },
    "Data Quality Issue Log": {
        "Issue Category": {
            "data_type": "string",
            "expression": (
                "SWITCH ( TRUE (), "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"duplicate\" ), \"Duplicate keys\", "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"foreign_key\" ), \"Referential integrity\", "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"missing\" ), \"Missing values\", "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"domain\" ), \"Invalid domain values\", "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"anomaly\" ), \"Pricing anomalies\", "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"date\" ), \"Invalid dates\", "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"whitespace\" ) || "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"text\" ), \"Standardisation\", "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"mismatch\" ) || "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"removed\" ) || "
                "CONTAINSSTRING ( 'Data Quality Issue Log'[issue_type], \"sign_error\" ), \"Business-rule correction\", "
                '"Other" )'
            ),
            "format_string": None,
            "hidden": False,
        }
    },
    "Pipeline Run Summary": {
        "Pipeline Stage": {
            "data_type": "string",
            "expression": (
                "SWITCH ( 'Pipeline Run Summary'[table_name], "
                '"dim_customer", "Customer dimension", '
                '"dim_vehicle", "Vehicle dimension", '
                '"dim_dealer", "Dealer dimension", '
                '"fact_inquiry", "Inquiry fact", '
                '"fact_quote", "Quote fact", '
                '"dim_date", "Date dimension", "Other" )'
            ),
            "format_string": None,
            "hidden": False,
        }
    },
}


MEASURES = [
    (
        "Total Inquiries",
        "DISTINCTCOUNT ( 'Fact Inquiry'[inquiry_id] )",
        "#,##0",
        "Volume",
    ),
    ("Total Quotes", "DISTINCTCOUNT ( 'Fact Quote'[quote_id] )", "#,##0", "Volume"),
    (
        "Total Quotes by Quote Date",
        "CALCULATE ( [Total Quotes], USERELATIONSHIP ( 'Dim Date'[date], 'Fact Quote'[quote_date] ), CROSSFILTER ( 'Dim Date'[date], 'Fact Inquiry'[inquiry_date], NONE ) )",
        "#,##0",
        "Volume",
    ),
    (
        "Converted Inquiries",
        "CALCULATE ( [Total Inquiries], KEEPFILTERS ( 'Fact Inquiry'[conversion_flag] = TRUE () ) )",
        "#,##0",
        "Conversion",
    ),
    (
        "Conversion Rate",
        "DIVIDE ( [Converted Inquiries], [Total Inquiries] )",
        "0.0%",
        "Conversion",
    ),
    (
        "Average Quotes per Inquiry",
        "DIVIDE ( [Total Quotes], [Total Inquiries] )",
        "0.00",
        "Volume",
    ),
    (
        "Average Days to Conversion",
        "CALCULATE ( AVERAGE ( 'Fact Inquiry'[days_to_conversion] ), KEEPFILTERS ( 'Fact Inquiry'[conversion_flag] = TRUE () ) )",
        '0.0 "days"',
        "Conversion",
    ),
    (
        "Inquiries Under 8h SLA",
        "CALCULATE ( [Total Inquiries], KEEPFILTERS ( 'Fact Inquiry'[fastest_response_hours] < 8 ) )",
        "#,##0",
        "Conversion",
    ),
    (
        "8h SLA Compliance Rate",
        "DIVIDE ( [Inquiries Under 8h SLA], [Total Inquiries] )",
        "0.0%",
        "Conversion",
    ),
    ("Average Quote", "AVERAGE ( 'Fact Quote'[quote_amount] )", "CHF #,##0", "Pricing"),
    ("Maximum Quote", "MAX ( 'Fact Quote'[quote_amount] )", "CHF #,##0", "Pricing"),
    ("Minimum Quote", "MIN ( 'Fact Quote'[quote_amount] )", "CHF #,##0", "Pricing"),
    ("Median Quote", "MEDIAN ( 'Fact Quote'[quote_amount] )", "CHF #,##0", "Pricing"),
    (
        "Average Highest Quote",
        "AVERAGE ( 'Fact Inquiry'[highest_quote] )",
        "CHF #,##0",
        "Pricing",
    ),
    (
        "Average Lowest Quote",
        "AVERAGE ( 'Fact Inquiry'[lowest_quote] )",
        "CHF #,##0",
        "Pricing",
    ),
    (
        "Average Quote Spread",
        "AVERAGE ( 'Fact Inquiry'[quote_spread] )",
        "CHF #,##0",
        "Pricing",
    ),
    (
        "Average Quote Spread %",
        "AVERAGE ( 'Fact Inquiry'[quote_spread_pct] )",
        "0.0%",
        "Pricing",
    ),
    (
        "Average Sale Value",
        "CALCULATE ( AVERAGE ( 'Fact Inquiry'[final_sale_price] ), KEEPFILTERS ( 'Fact Inquiry'[conversion_flag] = TRUE () ) )",
        "CHF #,##0",
        "Pricing",
    ),
    (
        "Total Accepted Quote Value",
        "CALCULATE ( SUM ( 'Fact Quote'[quote_amount] ), KEEPFILTERS ( 'Fact Quote'[accepted_flag] = TRUE () ) )",
        "CHF #,##0",
        "Pricing",
    ),
    (
        "Quote-to-Market Ratio",
        "DIVIDE ( SUM ( 'Fact Quote'[quote_amount] ), SUM ( 'Fact Quote'[estimated_market_value] ) )",
        "0.0%",
        "Pricing",
    ),
    (
        "Average Estimated Market Value",
        "AVERAGE ( 'Fact Quote'[estimated_market_value] )",
        "CHF #,##0",
        "Pricing",
    ),
    (
        "Quote Anomalies",
        "CALCULATE ( [Total Quotes], KEEPFILTERS ( 'Fact Quote'[anomaly_flag] = TRUE () ) )",
        "#,##0",
        "Pricing",
    ),
    (
        "Quote Anomaly Rate",
        "DIVIDE ( [Quote Anomalies], [Total Quotes] )",
        "0.00%",
        "Pricing",
    ),
    (
        "Average Response Time",
        "AVERAGE ( 'Fact Quote'[response_time_hours] )",
        '0.0 "h"',
        "Dealer",
    ),
    (
        "Average Fastest Response Time",
        "AVERAGE ( 'Fact Inquiry'[fastest_response_hours] )",
        '0.0 "h"',
        "Dealer",
    ),
    (
        "Dealer Wins",
        "CALCULATE ( [Total Quotes], KEEPFILTERS ( 'Fact Quote'[accepted_flag] = TRUE () ) )",
        "#,##0",
        "Dealer",
    ),
    ("Dealer Win Rate", "DIVIDE ( [Dealer Wins], [Total Quotes] )", "0.0%", "Dealer"),
    (
        "Average Dealer Competitiveness",
        "AVERAGE ( 'Fact Quote'[quote_to_market_ratio] )",
        "0.0%",
        "Dealer",
    ),
    (
        "Dealer Accepted Value",
        "CALCULATE ( SUM ( 'Fact Quote'[quote_amount] ), KEEPFILTERS ( 'Fact Quote'[accepted_flag] = TRUE () ) )",
        "CHF #,##0",
        "Dealer",
    ),
    (
        "Active Dealers",
        "CALCULATE ( DISTINCTCOUNT ( 'Dim Dealer'[dealer_id] ), KEEPFILTERS ( 'Dim Dealer'[active_flag] = TRUE () ) )",
        "#,##0",
        "Dealer",
    ),
    (
        "Dealer Rank",
        "IF ( [Total Quotes] >= 250, RANKX ( FILTER ( ALLSELECTED ( 'Dim Dealer'[dealer_id], 'Dim Dealer'[dealer_name] ), CALCULATE ( [Total Quotes] ) >= 250 ), [Dealer Win Rate], , DESC, DENSE ) )",
        "#,##0",
        "Dealer",
    ),
    (
        "Dealer Win Rate Top 7",
        "IF ( [Dealer Rank] <= 7, [Dealer Win Rate] )",
        "0.0%",
        "Dealer",
    ),
    (
        "Dealer Accepted Value Top 5",
        "VAR DealerValueRank = RANKX ( FILTER ( ALLSELECTED ( 'Dim Dealer'[dealer_id], 'Dim Dealer'[dealer_name] ), CALCULATE ( [Total Quotes] ) >= 250 ), [Dealer Accepted Value], , DESC, DENSE ) RETURN IF ( DealerValueRank <= 5, [Dealer Accepted Value] )",
        "CHF #,##0",
        "Dealer",
    ),
    (
        "Previous Month Inquiries",
        "CALCULATE ( [Total Inquiries], DATEADD ( 'Dim Date'[date], -1, MONTH ) )",
        "#,##0",
        "Time Intelligence",
    ),
    (
        "Month-over-Month Inquiry Growth",
        "DIVIDE ( [Total Inquiries] - [Previous Month Inquiries], [Previous Month Inquiries] )",
        "+0.0%;-0.0%;0.0%",
        "Time Intelligence",
    ),
    (
        "Previous Year Inquiries",
        "CALCULATE ( [Total Inquiries], SAMEPERIODLASTYEAR ( 'Dim Date'[date] ) )",
        "#,##0",
        "Time Intelligence",
    ),
    (
        "Year-over-Year Inquiry Growth",
        "DIVIDE ( [Total Inquiries] - [Previous Year Inquiries], [Previous Year Inquiries] )",
        "+0.0%;-0.0%;0.0%",
        "Time Intelligence",
    ),
    (
        "Previous Month Conversion Rate",
        "CALCULATE ( [Conversion Rate], DATEADD ( 'Dim Date'[date], -1, MONTH ) )",
        "0.0%",
        "Time Intelligence",
    ),
    (
        "Conversion Rate Change",
        "[Conversion Rate] - [Previous Month Conversion Rate]",
        "+0.0%;-0.0%;0.0%",
        "Time Intelligence",
    ),
    (
        "Rolling 3M Conversion Rate",
        "VAR LastVisibleDate = MAX ( 'Dim Date'[date] ) VAR ThreeMonthWindow = DATESINPERIOD ( 'Dim Date'[date], LastVisibleDate, -3, MONTH ) RETURN DIVIDE ( CALCULATE ( [Converted Inquiries], ThreeMonthWindow ), CALCULATE ( [Total Inquiries], ThreeMonthWindow ) )",
        "0.0%",
        "Time Intelligence",
    ),
    (
        "Data Quality Metric Rate",
        "MAX ( 'Data Quality Metrics'[rate] )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Raw Data Quality Rate",
        "CALCULATE ( [Data Quality Metric Rate], REMOVEFILTERS ( 'Data Quality Metrics'[stage] ), 'Data Quality Metrics'[stage] = \"Raw\" )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Raw Data Quality Score",
        "CALCULATE ( [Data Quality Metric Rate], REMOVEFILTERS ( 'Data Quality Metrics'[stage] ), REMOVEFILTERS ( 'Data Quality Metrics'[metric_name] ), 'Data Quality Metrics'[stage] = \"Raw\", 'Data Quality Metrics'[metric_name] = \"overall_data_quality_score\" )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Processed Data Quality Rate",
        "CALCULATE ( [Data Quality Metric Rate], REMOVEFILTERS ( 'Data Quality Metrics'[stage] ), 'Data Quality Metrics'[stage] = \"Processed\" )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Data Quality Improvement",
        "( [Processed Data Quality Rate] - [Raw Data Quality Rate] ) * 100",
        '+0.000 "pp";-0.000 "pp";0.000 "pp"',
        "Data Quality",
    ),
    (
        "Data Quality Score",
        "CALCULATE ( [Data Quality Metric Rate], 'Data Quality Metrics'[stage] = \"Processed\", 'Data Quality Metrics'[metric_name] = \"overall_data_quality_score\" )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Completeness Rate",
        "CALCULATE ( [Data Quality Metric Rate], 'Data Quality Metrics'[stage] = \"Processed\", 'Data Quality Metrics'[metric_name] = \"completeness_rate\" )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Validity Rate",
        "CALCULATE ( [Data Quality Metric Rate], 'Data Quality Metrics'[stage] = \"Processed\", 'Data Quality Metrics'[metric_name] = \"validity_rate\" )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Uniqueness Rate",
        "CALCULATE ( [Data Quality Metric Rate], 'Data Quality Metrics'[stage] = \"Processed\", 'Data Quality Metrics'[metric_name] = \"uniqueness_rate\" )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Referential Integrity Rate",
        "CALCULATE ( [Data Quality Metric Rate], 'Data Quality Metrics'[stage] = \"Processed\", 'Data Quality Metrics'[metric_name] = \"referential_integrity_rate\" )",
        "0.000%",
        "Data Quality",
    ),
    (
        "Affected Rows",
        "SUM ( 'Data Quality Issue Log'[affected_rows] )",
        "#,##0",
        "Data Quality",
    ),
    (
        "Raw Records",
        "SUM ( 'Pipeline Run Summary'[raw_records] )",
        "#,##0",
        "Data Quality",
    ),
    (
        "Clean Records",
        "SUM ( 'Pipeline Run Summary'[clean_records] )",
        "#,##0",
        "Data Quality",
    ),
    (
        "Rejected Records",
        "SUM ( 'Pipeline Run Summary'[quarantined_records] )",
        "#,##0",
        "Data Quality",
    ),
    (
        "Loaded Records",
        "SUM ( 'Pipeline Run Summary'[loaded_records] )",
        "#,##0",
        "Data Quality",
    ),
]


MEASURES_BY_HOME_TABLE: dict[str, tuple[str, ...]] = {
    "Fact Inquiry": (
        "Total Inquiries",
        "Converted Inquiries",
        "Conversion Rate",
        "Average Quotes per Inquiry",
        "Average Days to Conversion",
        "Inquiries Under 8h SLA",
        "8h SLA Compliance Rate",
        "Average Highest Quote",
        "Average Lowest Quote",
        "Average Quote Spread",
        "Average Quote Spread %",
        "Average Sale Value",
        "Average Fastest Response Time",
        "Previous Month Inquiries",
        "Month-over-Month Inquiry Growth",
        "Previous Year Inquiries",
        "Year-over-Year Inquiry Growth",
        "Previous Month Conversion Rate",
        "Conversion Rate Change",
        "Rolling 3M Conversion Rate",
    ),
    "Fact Quote": (
        "Total Quotes",
        "Total Quotes by Quote Date",
        "Average Quote",
        "Maximum Quote",
        "Minimum Quote",
        "Median Quote",
        "Total Accepted Quote Value",
        "Quote-to-Market Ratio",
        "Average Estimated Market Value",
        "Quote Anomalies",
        "Quote Anomaly Rate",
    ),
    "Dim Dealer": (
        "Average Response Time",
        "Dealer Wins",
        "Dealer Win Rate",
        "Average Dealer Competitiveness",
        "Dealer Accepted Value",
        "Active Dealers",
        "Dealer Rank",
        "Dealer Win Rate Top 7",
        "Dealer Accepted Value Top 5",
    ),
    "Data Quality Metrics": (
        "Data Quality Metric Rate",
        "Raw Data Quality Rate",
        "Raw Data Quality Score",
        "Processed Data Quality Rate",
        "Data Quality Improvement",
        "Data Quality Score",
        "Completeness Rate",
        "Validity Rate",
        "Uniqueness Rate",
        "Referential Integrity Rate",
    ),
    "Data Quality Issue Log": ("Affected Rows",),
    "Pipeline Run Summary": (
        "Raw Records",
        "Clean Records",
        "Rejected Records",
        "Loaded Records",
    ),
}
MEASURE_HOME_TABLES = {
    measure_name: table_name
    for table_name, measure_names in MEASURES_BY_HOME_TABLE.items()
    for measure_name in measure_names
}


RELATIONSHIPS = [
    ("Inquiry Date", "Fact Inquiry.inquiry_date", "Dim Date.date", True),
    ("Inquiry Customer", "Fact Inquiry.customer_id", "Dim Customer.customer_id", True),
    ("Inquiry Vehicle", "Fact Inquiry.vehicle_id", "Dim Vehicle.vehicle_id", True),
    ("Quote Inquiry", "Fact Quote.inquiry_id", "Fact Inquiry.inquiry_id", True),
    ("Quote Dealer", "Fact Quote.dealer_id", "Dim Dealer.dealer_id", True),
    ("Quote Date", "Fact Quote.quote_date", "Dim Date.date", False),
]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _object_id(label: str) -> str:
    return hashlib.sha1(label.encode("utf-8")).hexdigest()[:20]


def _q(name: str) -> str:
    return f"'{name}'" if " " in name else name


def _column_expression(table: str, column: str) -> dict[str, Any]:
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": column,
        }
    }


def _measure_expression(measure: str) -> dict[str, Any]:
    return {
        "Measure": {
            "Expression": {
                "SourceRef": {"Entity": MEASURE_HOME_TABLES[measure]}
            },
            "Property": measure,
        }
    }


def _measure_query_ref(measure: str) -> str:
    return f"{MEASURE_HOME_TABLES[measure]}.{measure}"


def _projection(
    expression: dict[str, Any], query_ref: str, display_name: str
) -> dict[str, Any]:
    return {
        "field": expression,
        "queryRef": query_ref,
        "nativeQueryRef": display_name,
    }


def _column_projection(table: str, column: str, display_name: str) -> dict[str, Any]:
    return _projection(
        _column_expression(table, column), f"{table}.{column}", display_name
    )


def _measure_projection(measure: str, display_name: str | None = None) -> dict[str, Any]:
    return _projection(
        _measure_expression(measure),
        _measure_query_ref(measure),
        display_name or measure,
    )


def _bool(value: bool) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": str(value).lower()}}}


def _number(value: int | float) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": f"{value}D"}}}


def _text(value: str) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": f"'{value.replace(chr(39), chr(39) * 2)}'"}}}


def _color(value: str) -> dict[str, Any]:
    return {"solid": {"color": _text(value)}}


NAVY = "#16324F"
BLUE = "#2563EB"
TEAL = "#0F766E"
GREEN = "#15803D"
ORANGE = "#D97706"
RED = "#B91C1C"
TEXT = "#1F2937"
MUTED = "#64748B"
BORDER = "#D9E2EC"
GRID = "#E8EEF4"
WHITE = "#FFFFFF"

MEASURE_COLORS = {
    "Total Inquiries": BLUE,
    "Converted Inquiries": TEAL,
    "Conversion Rate": TEAL,
    "Dealer Win Rate": TEAL,
    "Dealer Win Rate Top 7": TEAL,
    "Dealer Accepted Value": BLUE,
    "Dealer Accepted Value Top 5": BLUE,
    "Total Accepted Quote Value": BLUE,
    "Quote-to-Market Ratio": TEAL,
    "Average Quote Spread": ORANGE,
    "Average Quote": BLUE,
    "Average Estimated Market Value": NAVY,
    "Data Quality Metric Rate": TEAL,
    "Affected Rows": ORANGE,
    "Raw Records": NAVY,
    "Clean Records": GREEN,
    "Rejected Records": RED,
}


def _container_format(title: str | None = None, padding: int = 8) -> dict[str, Any]:
    formatting: dict[str, Any] = {
        "background": [
            {
                "properties": {
                    "show": _bool(True),
                    "color": _color(WHITE),
                    "transparency": _number(0),
                }
            }
        ],
        "border": [
            {
                "properties": {
                    "show": _bool(True),
                    "color": _color(BORDER),
                    "radius": _number(6),
                    "width": _number(1),
                }
            }
        ],
        "padding": [
            {
                "properties": {
                    side: _number(padding)
                    for side in ("top", "bottom", "left", "right")
                }
            }
        ],
        "visualHeader": [{"properties": {"show": _bool(False)}}],
    }
    if title:
        formatting["title"] = [
            {
                "properties": {
                    "show": _bool(True),
                    "text": _text(title),
                    "heading": _text("Heading3"),
                    "titleWrap": _bool(True),
                    "fontColor": _color(NAVY),
                    "fontFamily": _text("Segoe UI Semibold"),
                    "fontSize": _number(11),
                    "bold": _bool(True),
                }
            }
        ]
    return formatting


def _visual(
    page: str,
    key: str,
    visual_type: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z: int,
    *,
    query_state: dict[str, Any] | None = None,
    objects: dict[str, Any] | None = None,
    container_objects: dict[str, Any] | None = None,
    sort_field: dict[str, Any] | None = None,
    sort_direction: str = "Descending",
) -> dict[str, Any]:
    visual: dict[str, Any] = {"visualType": visual_type}
    if query_state is not None:
        query: dict[str, Any] = {"queryState": query_state}
        if sort_field is not None:
            query["sortDefinition"] = {
                "sort": [{"field": sort_field, "direction": sort_direction}],
                "isDefaultSort": True,
            }
        visual["query"] = query
        visual["drillFilterOtherVisuals"] = True
    if objects:
        visual["objects"] = objects
    if container_objects:
        visual["visualContainerObjects"] = container_objects
    return {
        "$schema": f"{REPORT_SCHEMA}/visualContainer/2.9.0/schema.json",
        "name": _object_id(f"{page}-{key}"),
        "position": {
            "x": x,
            "y": y,
            "z": z,
            "height": height,
            "width": width,
            "tabOrder": z,
        },
        "visual": visual,
    }


def _textbox(
    page: str,
    key: str,
    x: int,
    y: int,
    width: int,
    height: int,
    paragraphs: list[tuple[str, str, str, str]],
    z: int,
) -> dict[str, Any]:
    text_paragraphs = [
        {
            "textRuns": [
                {
                    "value": value,
                    "textStyle": {
                        "fontFamily": font,
                        "fontSize": size,
                        "color": color,
                    },
                }
            ],
            "horizontalTextAlignment": "left",
        }
        for value, font, size, color in paragraphs
    ]
    return _visual(
        page,
        key,
        "textbox",
        x,
        y,
        width,
        height,
        z,
        objects={"general": [{"properties": {"paragraphs": text_paragraphs}}]},
        container_objects={
            "background": [{"properties": {"show": _bool(False)}}],
            "border": [{"properties": {"show": _bool(False)}}],
            "padding": [
                {
                    "properties": {
                        side: _number(0)
                        for side in ("top", "bottom", "left", "right")
                    }
                }
            ],
            "visualHeader": [{"properties": {"show": _bool(False)}}],
        },
    )


def _page_title(page: str, title: str, subtitle: str, width: int) -> dict[str, Any]:
    return _textbox(
        page,
        "page-title",
        24,
        16,
        width,
        64,
        [
            (title, "Segoe UI Semibold", "22px", NAVY),
            (subtitle, "Segoe UI", "10px", MUTED),
        ],
        100,
    )


def _insight_callout(
    page: str,
    title: str,
    body: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z: int,
) -> dict[str, Any]:
    visual = _textbox(
        page,
        "insight-callout",
        x,
        y,
        width,
        height,
        [
            (title, "Segoe UI Semibold", "13px", NAVY),
            (body, "Segoe UI", "10px", TEXT),
        ],
        z,
    )
    visual["visual"]["visualContainerObjects"] = {
        "background": [
            {
                "properties": {
                    "show": _bool(True),
                    "color": _color("#EFF6FF"),
                    "transparency": _number(0),
                }
            }
        ],
        "border": [
            {
                "properties": {
                    "show": _bool(True),
                    "color": _color("#BFDBFE"),
                    "radius": _number(6),
                    "width": _number(1),
                }
            }
        ],
        "padding": [
            {
                "properties": {
                    side: _number(12)
                    for side in ("top", "bottom", "left", "right")
                }
            }
        ],
        "visualHeader": [{"properties": {"show": _bool(False)}}],
    }
    return visual


def _slicer(
    page: str,
    key: str,
    table: str,
    column: str,
    display_name: str,
    x: int,
    width: int,
    *,
    mode: str = "Dropdown",
    z: int = 200,
) -> dict[str, Any]:
    return _visual(
        page,
        key,
        "slicer",
        x,
        8,
        width,
        80,
        z,
        query_state={
            "Values": {
                "projections": [_column_projection(table, column, display_name)]
            }
        },
        objects={
            "data": [{"properties": {"mode": _text(mode)}}],
            "header": [
                {
                    "properties": {
                        "show": _bool(True),
                        "text": _text(display_name),
                        "fontFamily": _text("Segoe UI Semibold"),
                        "textSize": _number(9),
                        "fontColor": _color(TEXT),
                    }
                }
            ],
            "items": [
                {
                    "properties": {
                        "fontFamily": _text("Segoe UI"),
                        "textSize": _number(9),
                        "fontColor": _color(TEXT),
                    }
                }
            ],
        },
        container_objects=_container_format(padding=0),
    )


def _cards(
    page: str,
    measures: list[
        tuple[str, str, str | None] | tuple[str, str, str | None, str]
    ],
) -> list[dict[str, Any]]:
    """Build one native card per KPI so every value has a stable data role."""

    gap = 8
    available_width = 1232
    card_width = (available_width - gap * (len(measures) - 1)) // len(measures)
    cards: list[dict[str, Any]] = []
    for index, measure_spec in enumerate(measures):
        measure, label, custom_format, *visual_keys = measure_spec
        visual_key = visual_keys[0] if visual_keys else measure
        x = 24 + index * (card_width + gap)
        width = 1256 - x if index == len(measures) - 1 else card_width
        value_properties = {
            "show": _bool(True),
            "fontFamily": _text("Segoe UI Semibold"),
            "fontSize": _number(20),
            "bold": _bool(True),
            "fontColor": _color(NAVY),
            "labelDisplayUnits": _number(0),
        }
        if custom_format:
            value_properties["customFormatString"] = _text(custom_format)
        card_selector = {"id": "default"}
        cards.append(
            _visual(
                page,
                f"kpi-{visual_key}",
                "cardVisual",
                x,
                96,
                width,
                96,
                300 + index,
                query_state={
                    "Data": {
                        "projections": [_measure_projection(measure, label)]
                    }
                },
                objects={
                    "cardCalloutArea": [
                        {
                            "properties": {
                                "show": _bool(True),
                                "backgroundFillColor": _color(WHITE),
                                "backgroundTransparency": _number(0),
                                "paddingUniform": _number(4),
                                "rectangleRoundedCurve": _number(4),
                            }
                        }
                    ],
                    "value": [
                        {
                            "properties": value_properties,
                            "selector": card_selector,
                        }
                    ],
                    "label": [
                        {
                            "properties": {
                                "show": _bool(True),
                                "text": _text(label),
                                "fontFamily": _text("Segoe UI Semibold"),
                                "fontSize": _number(10),
                                "bold": _bool(True),
                                "fontColor": _color(NAVY),
                                "position": _text("aboveValue"),
                                "textWrap": _bool(False),
                            },
                            "selector": card_selector,
                        }
                    ],
                    "padding": [
                        {
                            "properties": {
                                "paddingSelection": _text("Custom"),
                                "paddingUniform": _number(0),
                                "paddingIndividual": _bool(False),
                            },
                            "selector": card_selector,
                        }
                    ],
                    "layout": [
                        {
                            "properties": {
                                "paddingUniform": _number(0),
                                "paddingIndividual": _bool(False),
                            },
                            "selector": card_selector,
                        }
                    ],
                    "spacing": [
                        {
                            "properties": {"verticalSpacing": _number(0)},
                            "selector": card_selector,
                        }
                    ],
                    "outline": [
                        {
                            "properties": {"show": _bool(False)},
                            "selector": card_selector,
                        }
                    ],
                },
                container_objects=_container_format(padding=4),
            )
        )
    return cards


def _chart_objects(
    visual_type: str,
    measures: list[str],
    *,
    show_labels: bool,
    show_legend: bool,
    axis_display_units: int | None = None,
    label_precision: int | None = None,
    data_label_format: str | None = None,
    category_font_size: int = 9,
    category_max_margin: int | None = None,
) -> dict[str, Any]:
    category_axis_properties = {
        "fontFamily": _text("Segoe UI"),
        "fontSize": _number(category_font_size),
        "labelColor": _color(TEXT),
        "showAxisTitle": _bool(False),
    }
    if category_max_margin is not None:
        category_axis_properties["maxMarginFactor"] = _number(category_max_margin)
    value_axis_properties = {
        "fontFamily": _text("Segoe UI"),
        "fontSize": _number(9),
        "labelColor": _color(MUTED),
        "showAxisTitle": _bool(False),
        "gridlineShow": _bool(True),
        "gridlineColor": _color(GRID),
        "gridlineThickness": _number(1),
    }
    if axis_display_units is not None:
        value_axis_properties["labelDisplayUnits"] = _number(axis_display_units)
        if visual_type == "scatterChart":
            category_axis_properties["labelDisplayUnits"] = _number(
                axis_display_units
            )
    if label_precision is not None:
        value_axis_properties["labelPrecision"] = _number(label_precision)
        if visual_type == "scatterChart":
            category_axis_properties["labelPrecision"] = _number(label_precision)
    objects: dict[str, Any] = {
        "categoryAxis": [{"properties": category_axis_properties}],
        "valueAxis": [{"properties": value_axis_properties}],
        "legend": [
            {
                "properties": {
                    "show": _bool(show_legend),
                    "position": _text("Top"),
                    "showTitle": _bool(False),
                    "fontFamily": _text("Segoe UI"),
                    "fontSize": _number(9),
                    "labelColor": _color(TEXT),
                }
            }
        ],
    }
    if visual_type != "scatterChart":
        label_properties = {
            "show": _bool(show_labels),
            "fontFamily": _text("Segoe UI"),
            "fontSize": _number(8),
            "color": _color(TEXT),
            "labelPosition": _text("OutsideEnd"),
            "optimizeLabelDisplay": _bool(True),
        }
        if data_label_format:
            label_properties["labelDisplayUnits"] = _number(0)
            label_properties["valueCustomFormatString"] = _text(data_label_format)
        elif axis_display_units is not None:
            label_properties["labelDisplayUnits"] = _number(axis_display_units)
        if label_precision is not None:
            label_properties["labelPrecision"] = _number(label_precision)
        objects["labels"] = [
            {"properties": label_properties}
        ]
    if visual_type == "lineChart":
        objects["lineStyles"] = []
        for measure in measures:
            color = MEASURE_COLORS.get(measure, BLUE)
            objects["lineStyles"].append(
                {
                    "properties": {
                        "strokeShow": _bool(True),
                        "strokeWidth": _number(2),
                        "strokeColor": _color(color),
                        "showMarker": _bool(True),
                        "markerShape": _text("circle"),
                        "markerSize": _number(5),
                        "markerColor": _color(color),
                    },
                    "selector": {"metadata": _measure_query_ref(measure)},
                }
            )
    elif visual_type == "scatterChart":
        objects["dataPoint"] = [
            {"properties": {"defaultColor": _color(BLUE)}}
        ]
        objects["categoryLabels"] = [
            {
                "properties": {
                    "show": _bool(False),
                    "fontFamily": _text("Segoe UI"),
                    "fontSize": _number(8),
                    "color": _color(TEXT),
                }
            }
        ]
    else:
        objects["dataPoint"] = [
            {
                "properties": {"fill": _color(MEASURE_COLORS.get(measure, BLUE))},
                "selector": {"metadata": _measure_query_ref(measure)},
            }
            for measure in measures
        ]
    return objects


def _cartesian(
    page: str,
    key: str,
    visual_type: str,
    title: str,
    category: tuple[str, str, str],
    measures: list[tuple[str, str]],
    x: int,
    y: int,
    width: int,
    height: int,
    z: int,
    *,
    series: tuple[str, str, str] | None = None,
    tooltips: list[tuple[str, str]] | None = None,
    show_labels: bool = False,
    sort_measure: str | None = None,
    sort_ascending: bool = False,
    axis_display_units: int | None = None,
    label_precision: int | None = None,
    data_label_format: str | None = None,
    category_font_size: int = 9,
    category_max_margin: int | None = None,
) -> dict[str, Any]:
    table, column, category_label = category
    query_state: dict[str, Any] = {
        "Category": {
            "projections": [_column_projection(table, column, category_label)]
        },
        "Y": {
            "projections": [
                _measure_projection(measure, label) for measure, label in measures
            ]
        },
    }
    if series:
        series_table, series_column, series_label = series
        query_state["Series"] = {
            "projections": [
                _column_projection(series_table, series_column, series_label)
            ]
        }
    if tooltips:
        query_state["Tooltips"] = {
            "projections": [
                _measure_projection(measure, label) for measure, label in tooltips
            ]
        }
    measure_names = [measure for measure, _ in measures]
    return _visual(
        page,
        key,
        visual_type,
        x,
        y,
        width,
        height,
        z,
        query_state=query_state,
        objects=_chart_objects(
            visual_type,
            measure_names,
            show_labels=show_labels,
            show_legend=bool(series or len(measures) > 1),
            axis_display_units=axis_display_units,
            label_precision=label_precision,
            data_label_format=data_label_format,
            category_font_size=category_font_size,
            category_max_margin=category_max_margin,
        ),
        container_objects=_container_format(title),
        sort_field=_measure_expression(sort_measure) if sort_measure else None,
        sort_direction="Ascending" if sort_ascending else "Descending",
    )


def _scatter(
    page: str,
    key: str,
    title: str,
    x_measure: tuple[str, str],
    y_measure: tuple[str, str],
    category: tuple[str, str, str],
    x: int,
    y: int,
    width: int,
    height: int,
    z: int,
    *,
    size_measure: tuple[str, str] | None = None,
    series: tuple[str, str, str] | None = None,
    tooltips: list[tuple[str, str]] | None = None,
    axis_display_units: int | None = None,
    label_precision: int | None = None,
    x_axis_title: str | None = None,
    y_axis_title: str | None = None,
) -> dict[str, Any]:
    category_table, category_column, category_label = category
    query_state: dict[str, Any] = {
        "X": {"projections": [_measure_projection(*x_measure)]},
        "Y": {"projections": [_measure_projection(*y_measure)]},
        "Category": {
            "projections": [
                _column_projection(category_table, category_column, category_label)
            ]
        },
    }
    if size_measure:
        query_state["Size"] = {
            "projections": [_measure_projection(*size_measure)]
        }
    if series:
        series_table, series_column, series_label = series
        query_state["Series"] = {
            "projections": [
                _column_projection(series_table, series_column, series_label)
            ]
        }
    if tooltips:
        query_state["Tooltips"] = {
            "projections": [
                _measure_projection(measure, label) for measure, label in tooltips
            ]
        }
    objects = _chart_objects(
        "scatterChart",
        [x_measure[0], y_measure[0]],
        show_labels=False,
        show_legend=bool(series),
        axis_display_units=axis_display_units,
        label_precision=label_precision,
    )
    if x_axis_title:
        objects["categoryAxis"][0]["properties"].update(
            {
                "showAxisTitle": _bool(True),
                "titleText": _text(x_axis_title),
                "axisStyle": _text("showTitleOnly"),
            }
        )
    if y_axis_title:
        objects["valueAxis"][0]["properties"].update(
            {
                "showAxisTitle": _bool(True),
                "titleText": _text(y_axis_title),
                "axisStyle": _text("showTitleOnly"),
            }
        )
    return _visual(
        page,
        key,
        "scatterChart",
        x,
        y,
        width,
        height,
        z,
        query_state=query_state,
        objects=objects,
        container_objects=_container_format(title),
    )


def _table_visual(
    page: str,
    key: str,
    title: str,
    columns: list[tuple[str, str, str]],
    measures: list[tuple[str, str]],
    x: int,
    y: int,
    width: int,
    height: int,
    z: int,
    *,
    sort_measure: str | None = None,
    show_totals: bool = False,
    font_size: int = 9,
    conditional_measure: str | None = None,
) -> dict[str, Any]:
    projections = [
        _column_projection(table, column, label) for table, column, label in columns
    ]
    projections.extend(
        _measure_projection(measure, label) for measure, label in measures
    )
    container = _container_format(title)
    container["stylePreset"] = [{"properties": {"name": _text("None")}}]
    value_objects: list[dict[str, Any]] = [
        {
            "properties": {
                "fontFamily": _text("Segoe UI"),
                "fontSize": _number(font_size),
                "fontColorPrimary": _color(TEXT),
                "fontColorSecondary": _color(TEXT),
                "backColorPrimary": _color(WHITE),
                "backColorSecondary": _color("#F4F7FA"),
                "wordWrap": _bool(False),
            }
        }
    ]
    if conditional_measure:
        query_ref = _measure_query_ref(conditional_measure)
        value_objects.append(
            {
                "properties": {
                    "backColor": {
                        "solid": {
                            "color": {
                                "expr": {
                                    "FillRule": {
                                        "Input": {
                                            "SelectRef": {
                                                "ExpressionName": query_ref
                                            }
                                        },
                                        "FillRule": {
                                            "linearGradient2": {
                                                "min": {
                                                    "color": {
                                                        "Literal": {
                                                            "Value": "'#EFF6FF'"
                                                        }
                                                    }
                                                },
                                                "max": {
                                                    "color": {
                                                        "Literal": {
                                                            "Value": "'#BFDBFE'"
                                                        }
                                                    }
                                                },
                                                "nullColoringStrategy": {
                                                    "strategy": {
                                                        "Literal": {
                                                            "Value": "'noColor'"
                                                        }
                                                    }
                                                },
                                            }
                                        },
                                    }
                                }
                            }
                        }
                    }
                },
                "selector": {
                    "data": [
                        {"dataViewWildcard": {"matchingOption": 1}}
                    ],
                    "metadata": query_ref,
                },
            }
        )
    return _visual(
        page,
        key,
        "tableEx",
        x,
        y,
        width,
        height,
        z,
        query_state={"Values": {"projections": projections}},
        objects={
            "columnHeaders": [
                {
                    "properties": {
                        "autoSizeColumnWidth": _bool(True),
                        "columnAdjustment": _text("growToFit"),
                        "fontFamily": _text("Segoe UI Semibold"),
                        "fontSize": _number(font_size),
                        "fontColor": _color(WHITE),
                        "backColor": _color(NAVY),
                        "wordWrap": _bool(True),
                    }
                }
            ],
            "values": value_objects,
            "total": [{"properties": {"totals": _bool(show_totals)}}],
        },
        container_objects=container,
        sort_field=_measure_expression(sort_measure) if sort_measure else None,
    )


PAGE_SPECS = [
    {
        "name": "ExecutiveOverview",
        "display": "Executive Overview",
        "subtitle": "Commercial performance, channel quality, vehicle mix and dealer contribution",
        "visuals": 14,
    },
    {
        "name": "PricingCompetitiveness",
        "display": "Pricing & Competitiveness",
        "subtitle": "Quote positioning against market value and spread by vehicle segment",
        "visuals": 12,
    },
    {
        "name": "CustomerConversion",
        "display": "Customer & Conversion",
        "subtitle": "Lead-source quality, response speed and customer conversion drivers",
        "visuals": 13,
    },
    {
        "name": "DealerPerformance",
        "display": "Dealer Performance",
        "subtitle": "Win rate, response speed, quote volume and accepted-value outliers",
        "visuals": 11,
    },
    {
        "name": "DataQualityOperations",
        "display": "Data Quality & Operations",
        "subtitle": "Raw-to-curated controls, issue remediation and load reconciliation",
        "visuals": 9,
    },
]


def _build_model() -> None:
    definition = MODEL_DIR / "definition"
    tables_dir = definition / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    obsolete_tables = [tables_dir / "Measures.tmdl"]
    for pattern in ("LocalDateTable_*.tmdl", "DateTableTemplate_*.tmdl"):
        obsolete_tables.extend(tables_dir.glob(pattern))
    for obsolete_table in obsolete_tables:
        if obsolete_table.exists():
            obsolete_table.unlink()
    _write_json(
        MODEL_DIR / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {"qnaEnabled": True},
        },
    )
    _write_json(
        MODEL_DIR / ".platform",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.1.0/schema.json",
            "metadata": {
                "type": "SemanticModel",
                "displayName": "Automotive Commercial Analytics",
                "description": "PostgreSQL-backed automotive marketplace semantic model",
            },
            "config": {
                "version": "2.0",
                "logicalId": "a6de1b7e-7ad7-4f8f-b22e-bfe2d2fc9b61",
            },
        },
    )
    (definition / "database.tmdl").write_text(
        "database AutomotiveCommercialAnalytics\n"
        "\tcompatibilityLevel: 1702\n"
        "\tcompatibilityMode: powerBI\n"
        "\tlanguage: 1033\n",
        encoding="utf-8",
    )
    model_lines = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "\tdiscourageImplicitMeasures",
        "",
    ]
    model_lines.extend(f"ref table {_q(name)}" for name in TABLES)
    (definition / "model.tmdl").write_text(
        "\n".join(model_lines) + "\n", encoding="utf-8"
    )
    (definition / "expressions.tmdl").write_text(
        'expression pServer = "localhost:5432" meta '
        '[IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        "\tlineageTag: 81d079cc-4e86-4af8-ae1b-285ff6b11112\n\n"
        "\tannotation PBI_ResultType = Text\n\n"
        'expression pDatabase = "automotive_analytics" meta '
        '[IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        "\tlineageTag: 83350acd-71b0-4d99-b45a-9b72a6e87866\n\n"
        "\tannotation PBI_ResultType = Text\n",
        encoding="utf-8",
    )

    for table_name, spec in TABLES.items():
        lines = [f"table {_q(table_name)}"]
        if spec.get("category"):
            lines.extend([f"\tdataCategory: {spec['category']}", ""])
        for column, (data_type, hidden) in spec["columns"].items():
            lines.extend(
                [
                    f"\tcolumn {_q(column)}",
                    f"\t\tdataType: {data_type}",
                    *(["\t\tisHidden"] if hidden else []),
                    "\t\tsummarizeBy: none",
                    f"\t\tsourceColumn: {column}",
                ]
            )
            if table_name == "Dim Date" and column == "date":
                lines.append("\t\tisKey")
            if table_name == "Dim Date" and column == "month_name":
                lines.append("\t\tsortByColumn: month")
            if data_type == "dateTime":
                lines.append("\t\tformatString: Short Date")
            lines.append("")
        for column, calculated in CALCULATED_COLUMNS.get(table_name, {}).items():
            lines.extend(
                [
                    f"\tcolumn {_q(column)} = {calculated['expression']}",
                    f"\t\tdataType: {calculated['data_type']}",
                    *(["\t\tisHidden"] if calculated["hidden"] else []),
                    "\t\tsummarizeBy: none",
                ]
            )
            if calculated.get("format_string"):
                lines.append(f"\t\tformatString: {calculated['format_string']}")
            if calculated.get("sort_by"):
                lines.append(f"\t\tsortByColumn: {_q(calculated['sort_by'])}")
            lines.append("")
        source_table = spec["source"]
        lines.extend(
            [
                f"\tpartition {_q(table_name)} = m",
                "\t\tmode: import",
                "\t\tsource =",
                "\t\t\tlet",
                '\t\t\t\tSource = PostgreSQL.Database(#"pServer", #"pDatabase", [CreateNavigationProperties=false]),',
                f'\t\t\t\tData = Source{{[Schema="automotive_analytics", Item="{source_table}"]}}[Data]',
                "\t\t\tin",
                "\t\t\t\tData",
            ]
        )
        (tables_dir / f"{table_name}.tmdl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    measure_lines: list[str] = []
    for home_table in MEASURES_BY_HOME_TABLE:
        measure_lines.extend([f"table {_q(home_table)}", ""])
        for name, expression, format_string, folder in MEASURES:
            if MEASURE_HOME_TABLES[name] != home_table:
                continue
            measure_lines.extend(
                [
                    f"\tmeasure {_q(name)} = {expression}",
                    f"\t\tformatString: {format_string}",
                    f"\t\tdisplayFolder: {folder}",
                    "",
                ]
            )
    (definition / "measures.tmdl").write_text(
        "\n".join(measure_lines) + "\n", encoding="utf-8"
    )

    relationship_lines: list[str] = []
    for name, from_ref, to_ref, active in RELATIONSHIPS:
        from_table, from_column = from_ref.split(".", maxsplit=1)
        to_table, to_column = to_ref.split(".", maxsplit=1)
        relationship_lines.extend(
            [
                f"relationship {_q(name)}",
                *(["\tisActive: false"] if not active else []),
                f"\tfromColumn: {_q(from_table)}.{_q(from_column)}",
                f"\ttoColumn: {_q(to_table)}.{_q(to_column)}",
                "",
            ]
        )
    (definition / "relationships.tmdl").write_text(
        "\n".join(relationship_lines), encoding="utf-8"
    )


def _executive_visuals(spec: dict[str, Any]) -> list[dict[str, Any]]:
    page = spec["name"]
    return [
        _page_title(page, spec["display"], spec["subtitle"], 488),
        _slicer(page, "date", "Dim Date", "date", "Date", 528, 216, mode="Between", z=201),
        _slicer(page, "region", "Dim Dealer", "dealer_region", "Region", 752, 160, z=202),
        _slicer(page, "vehicle", "Dim Vehicle", "vehicle_type", "Vehicle Type", 920, 160, z=203),
        _slicer(page, "lead-source", "Fact Inquiry", "lead_source", "Lead Source", 1088, 168, z=204),
        *_cards(
            page,
            [
                ("Total Inquiries", "Total Inquiries", '#,##0.0,"K"'),
                ("Conversion Rate", "Conversion Rate", "0.0%"),
                (
                    "Total Accepted Quote Value",
                    "Accepted Quote Value",
                    'CHF #,##0.0,,"M"',
                ),
                (
                    "Average Response Time",
                    "Average Response Time",
                    '0.0 "hours"',
                    "Converted Inquiries",
                ),
                ("Active Dealers", "Active Dealers", "#,##0", "Average Quotes per Inquiry"),
            ],
        ),
        _cartesian(
            page,
            "monthly-trend",
            "lineChart",
            "Monthly inquiry and conversion trend",
            ("Dim Date", "Month Start", "Month"),
            [
                ("Total Inquiries", "Inquiries"),
                ("Converted Inquiries", "Converted"),
            ],
            24,
            200,
            604,
            232,
            401,
            tooltips=[("Conversion Rate", "Conversion Rate")],
            sort_measure=None,
            sort_ascending=True,
        ),
        _cartesian(
            page,
            "lead-source-conversion",
            "barChart",
            "Conversion rate by lead source",
            ("Fact Inquiry", "lead_source", "Lead Source"),
            [("Conversion Rate", "Conversion Rate")],
            644,
            200,
            612,
            232,
            402,
            tooltips=[
                ("Total Inquiries", "Inquiries"),
                ("Converted Inquiries", "Converted"),
            ],
            show_labels=True,
            sort_measure="Conversion Rate",
        ),
        _cartesian(
            page,
            "vehicle-value",
            "clusteredColumnChart",
            "Accepted quote value by vehicle type",
            ("Dim Vehicle", "vehicle_type", "Vehicle Type"),
            [("Total Accepted Quote Value", "Accepted Value")],
            24,
            448,
            604,
            248,
            403,
            tooltips=[
                ("Total Inquiries", "Inquiries"),
                ("Conversion Rate", "Conversion Rate"),
            ],
            show_labels=True,
            sort_measure="Total Accepted Quote Value",
            axis_display_units=1_000_000,
            label_precision=1,
            data_label_format='CHF #,##0.0,,"M"',
        ),
        _cartesian(
            page,
            "top-dealers",
            "barChart",
            "Top 5 dealers by accepted value (250+ quotes)",
            ("Dim Dealer", "dealer_name", "Dealer"),
            [("Dealer Accepted Value Top 5", "Accepted Value")],
            644,
            448,
            612,
            248,
            404,
            tooltips=[
                ("Dealer Win Rate", "Win Rate"),
                ("Total Quotes", "Quotes"),
            ],
            show_labels=True,
            sort_measure="Dealer Accepted Value Top 5",
            axis_display_units=1_000_000,
            label_precision=1,
            data_label_format='CHF #,##0.0,,"M"',
            category_font_size=8,
            category_max_margin=38,
        ),
    ]


def _pricing_visuals(spec: dict[str, Any]) -> list[dict[str, Any]]:
    page = spec["name"]
    return [
        _page_title(page, spec["display"], spec["subtitle"], 592),
        _slicer(page, "date", "Dim Date", "date", "Date", 616, 216, mode="Between", z=201),
        _slicer(page, "vehicle", "Dim Vehicle", "vehicle_type", "Vehicle Type", 840, 192, z=202),
        _slicer(page, "region", "Dim Dealer", "dealer_region", "Region", 1040, 216, z=203),
        *_cards(
            page,
            [
                (
                    "Average Estimated Market Value",
                    "Average Market Value",
                    'CHF #,##0.0,"K"',
                    "Total Accepted Quote Value",
                ),
                ("Average Quote", "Average Quote", 'CHF #,##0.0,"K"'),
                ("Quote-to-Market Ratio", "Quote-to-Market Ratio", "0.0%"),
                (
                    "Average Quote Spread",
                    "Average Quote Spread",
                    'CHF #,##0.0,"K"',
                ),
            ],
        ),
        _cartesian(
            page,
            "ratio-by-region",
            "clusteredColumnChart",
            "Quote-to-market ratio by dealer region",
            ("Dim Dealer", "dealer_region", "Region"),
            [("Quote-to-Market Ratio", "Quote / Market")],
            24,
            200,
            376,
            232,
            401,
            tooltips=[("Average Quote", "Average Quote")],
            show_labels=True,
            sort_measure="Quote-to-Market Ratio",
        ),
        _cartesian(
            page,
            "spread-by-type",
            "clusteredColumnChart",
            "Average quote spread by vehicle type",
            ("Dim Vehicle", "vehicle_type", "Vehicle Type"),
            [("Average Quote Spread", "Avg Quote Spread")],
            416,
            200,
            376,
            232,
            402,
            tooltips=[("Average Quote Spread %", "Spread %")],
            show_labels=True,
            sort_measure="Average Quote Spread",
            axis_display_units=1_000,
            label_precision=1,
            data_label_format='CHF #,##0.0,"K"',
        ),
        _scatter(
            page,
            "market-vs-quote",
            "Market value vs average quote by brand and vehicle type",
            ("Average Estimated Market Value", "Market Value"),
            ("Average Quote", "Average Quote"),
            ("Dim Vehicle", "brand", "Brand"),
            808,
            200,
            448,
            232,
            403,
            size_measure=("Total Quotes", "Quotes"),
            series=("Dim Vehicle", "vehicle_type", "Vehicle Type"),
            tooltips=[("Quote-to-Market Ratio", "Quote / Market")],
            axis_display_units=1_000,
            label_precision=1,
            x_axis_title="Market Value (CHF)",
            y_axis_title="Average Quote (CHF)",
        ),
        _table_visual(
            page,
            "pricing-detail",
            "Pricing detail by vehicle segment",
            [
                ("Dim Vehicle", "vehicle_type", "Vehicle Type"),
                ("Dim Vehicle", "brand", "Brand"),
            ],
            [
                ("Average Estimated Market Value", "Market Value"),
                ("Average Quote", "Average Quote"),
                ("Quote-to-Market Ratio", "Quote / Market"),
                ("Average Quote Spread", "Spread"),
                ("Average Quote Spread %", "Spread %"),
            ],
            24,
            448,
            1232,
            248,
            404,
            sort_measure="Average Quote Spread",
        ),
    ]


def _customer_visuals(spec: dict[str, Any]) -> list[dict[str, Any]]:
    page = spec["name"]
    return [
        _page_title(page, spec["display"], spec["subtitle"], 592),
        _slicer(page, "date", "Dim Date", "date", "Date", 616, 216, mode="Between", z=201),
        _slicer(page, "lead-source", "Fact Inquiry", "lead_source", "Lead Source", 840, 192, z=202),
        _slicer(page, "vehicle", "Dim Vehicle", "vehicle_type", "Vehicle Type", 1040, 216, z=203),
        *_cards(
            page,
            [
                ("Total Inquiries", "Total Inquiries", '#,##0.0,"K"'),
                ("Converted Inquiries", "Converted Inquiries", '#,##0.0,"K"'),
                ("Conversion Rate", "Conversion Rate", "0.0%"),
                (
                    "Average Fastest Response Time",
                    "Average Response Time",
                    '0.0 "hours"',
                    "Average Days to Conversion",
                ),
            ],
        ),
        _cartesian(
            page,
            "lead-source-chart",
            "barChart",
            "Lead-source conversion performance",
            ("Fact Inquiry", "lead_source", "Lead Source"),
            [("Conversion Rate", "Conversion Rate")],
            24,
            200,
            604,
            232,
            401,
            tooltips=[
                ("Total Inquiries", "Inquiries"),
                ("Converted Inquiries", "Converted"),
                ("Average Sale Value", "Average Sale Value"),
            ],
            show_labels=True,
            sort_measure="Conversion Rate",
        ),
        _cartesian(
            page,
            "response-bands",
            "clusteredColumnChart",
            "Conversion rate by fastest-response band",
            ("Fact Inquiry", "Response Time Band", "Response Band"),
            [("Conversion Rate", "Conversion Rate")],
            644,
            200,
            612,
            232,
            402,
            tooltips=[("Total Inquiries", "Inquiries")],
            show_labels=True,
        ),
        _cartesian(
            page,
            "mileage-conversion",
            "barChart",
            "Conversion rate by mileage bracket",
            ("Dim Vehicle", "mileage_bracket", "Mileage Bracket"),
            [("Conversion Rate", "Conversion Rate")],
            24,
            448,
            360,
            248,
            403,
            tooltips=[("Total Inquiries", "Inquiries")],
            show_labels=True,
            sort_measure="Conversion Rate",
        ),
        _table_visual(
            page,
            "lead-detail",
            "Lead-source detail",
            [("Fact Inquiry", "lead_source", "Lead Source")],
            [
                ("Total Inquiries", "Inquiries"),
                ("Converted Inquiries", "Converted"),
                ("Conversion Rate", "Conversion Rate"),
                ("Average Fastest Response Time", "Avg Fastest Response"),
                ("Average Sale Value", "Sale Value"),
            ],
            400,
            448,
            568,
            248,
            404,
            sort_measure="Conversion Rate",
            font_size=8,
        ),
        _insight_callout(
            page,
            "Faster responses are associated with higher conversion",
            "Inquiries answered in under 8 hours converted at 33.27%, compared with 29.43% at 8 hours or more — a 3.84 percentage-point gap.\n\nRecommendation:\nPrioritise routing and dealer SLA alerts before leads cross the 8-hour threshold.",
            984,
            448,
            272,
            248,
            405,
        ),
    ]


def _dealer_visuals(spec: dict[str, Any]) -> list[dict[str, Any]]:
    page = spec["name"]
    return [
        _page_title(page, spec["display"], spec["subtitle"], 728),
        _slicer(page, "date", "Dim Date", "date", "Date", 752, 216, mode="Between", z=201),
        _slicer(page, "region", "Dim Dealer", "dealer_region", "Region", 976, 280, z=202),
        *_cards(
            page,
            [
                ("Total Quotes", "Total Quotes", '#,##0.0,"K"'),
                ("Dealer Wins", "Dealer Wins", '#,##0.0,"K"'),
                ("Dealer Win Rate", "Dealer Win Rate", "0.0%"),
                (
                    "Average Response Time",
                    "Average Response Time",
                    '0.0 "hours"',
                    "Active Dealers",
                ),
            ],
        ),
        _cartesian(
            page,
            "top-win-rate",
            "barChart",
            "Top 7 dealers by win rate (250+ quotes)",
            ("Dim Dealer", "dealer_name", "Dealer"),
            [("Dealer Win Rate Top 7", "Win Rate")],
            24,
            200,
            620,
            232,
            401,
            tooltips=[
                ("Total Quotes", "Quotes"),
                ("Average Response Time", "Avg Response"),
                ("Dealer Accepted Value", "Accepted Value"),
            ],
            show_labels=True,
            sort_measure="Dealer Win Rate Top 7",
            category_font_size=8,
            category_max_margin=42,
        ),
        _scatter(
            page,
            "response-vs-win-rate",
            "Dealer response time vs win rate",
            ("Average Response Time", "Avg Response"),
            ("Dealer Win Rate", "Win Rate"),
            ("Dim Dealer", "dealer_name", "Dealer"),
            660,
            200,
            596,
            232,
            402,
            size_measure=("Total Quotes", "Quotes"),
            series=("Dim Dealer", "dealer_region", "Region"),
            tooltips=[("Dealer Accepted Value", "Accepted Value")],
        ),
        _cartesian(
            page,
            "top-accepted-value",
            "barChart",
            "Top 5 dealers by accepted value (250+ quotes)",
            ("Dim Dealer", "dealer_name", "Dealer"),
            [("Dealer Accepted Value Top 5", "Accepted Value")],
            24,
            448,
            500,
            248,
            403,
            tooltips=[
                ("Dealer Win Rate", "Win Rate"),
                ("Average Dealer Competitiveness", "Quote / Market"),
            ],
            show_labels=True,
            sort_measure="Dealer Accepted Value Top 5",
            axis_display_units=1_000_000,
            label_precision=1,
            data_label_format='CHF #,##0.0,,"M"',
            category_font_size=8,
            category_max_margin=45,
        ),
        _table_visual(
            page,
            "dealer-detail",
            "Dealer detail and outlier review",
            [
                ("Dim Dealer", "dealer_name", "Dealer"),
                ("Dim Dealer", "dealer_region", "Region"),
                ("Dim Dealer", "dealer_rating", "Dealer Rating"),
            ],
            [
                ("Total Quotes", "Quotes"),
                ("Dealer Win Rate", "Win Rate"),
                ("Average Response Time", "Avg Response"),
                ("Average Dealer Competitiveness", "Quote / Market"),
                ("Dealer Accepted Value", "Accepted Value"),
            ],
            540,
            448,
            716,
            248,
            404,
            sort_measure="Dealer Win Rate",
            font_size=8,
        ),
    ]


def _data_quality_visuals(spec: dict[str, Any]) -> list[dict[str, Any]]:
    page = spec["name"]
    return [
        _page_title(page, spec["display"], spec["subtitle"], 1232),
        *_cards(
            page,
            [
                (
                    "Raw Data Quality Score",
                    "Raw Data Quality Score",
                    "0.000%",
                    "Raw Records",
                ),
                (
                    "Data Quality Score",
                    "Processed Data Quality Score",
                    "0.000%",
                ),
                (
                    "Rejected Records",
                    "Rejected Records",
                    '#,##0.0,"K"',
                ),
                (
                    "Loaded Records",
                    "Loaded Records",
                    '#,##0.0,"K"',
                    "Clean Records",
                ),
            ],
        ),
        _table_visual(
            page,
            "raw-vs-processed",
            "Raw-to-processed data quality improvement",
            [("Data Quality Metrics", "Metric Label", "Metric")],
            [
                ("Raw Data Quality Rate", "Raw"),
                ("Processed Data Quality Rate", "Processed"),
                ("Data Quality Improvement", "Improvement (pp)"),
            ],
            24,
            200,
            604,
            232,
            401,
            show_totals=False,
            conditional_measure="Data Quality Improvement",
        ),
        _cartesian(
            page,
            "issues",
            "barChart",
            "Affected rows by issue category",
            ("Data Quality Issue Log", "Issue Category", "Issue Category"),
            [("Affected Rows", "Affected Rows")],
            644,
            200,
            612,
            232,
            402,
            show_labels=True,
            sort_measure="Affected Rows",
        ),
        _cartesian(
            page,
            "record-flow",
            "clusteredColumnChart",
            "Pipeline record reconciliation",
            ("Pipeline Run Summary", "Pipeline Stage", "Pipeline Stage"),
            [
                ("Raw Records", "Records In"),
                ("Clean Records", "Records Out"),
                ("Rejected Records", "Rejected"),
            ],
            24,
            448,
            604,
            248,
            403,
            show_labels=False,
        ),
        _table_visual(
            page,
            "run-summary",
            "Pipeline run summary",
            [
                ("Pipeline Run Summary", "Pipeline Stage", "Stage"),
                ("Pipeline Run Summary", "load_status", "Load Status"),
            ],
            [
                ("Raw Records", "Records In"),
                ("Clean Records", "Records Out"),
                ("Rejected Records", "Rejected"),
                ("Loaded Records", "Loaded"),
            ],
            644,
            448,
            612,
            248,
            404,
            show_totals=False,
        ),
    ]


def _page_visuals(spec: dict[str, Any]) -> list[dict[str, Any]]:
    builders = {
        "ExecutiveOverview": _executive_visuals,
        "PricingCompetitiveness": _pricing_visuals,
        "CustomerConversion": _customer_visuals,
        "DealerPerformance": _dealer_visuals,
        "DataQualityOperations": _data_quality_visuals,
    }
    return builders[spec["name"]](spec)


def _build_report() -> None:
    definition = REPORT_DIR / "definition"
    pages_dir = definition / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        PBIP_PATH,
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{PROJECT_NAME}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    _write_json(
        REPORT_DIR / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {
                "byPath": {"path": f"../{PROJECT_NAME}.SemanticModel"}
            },
        },
    )
    _write_json(
        REPORT_DIR / ".platform",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.1.0/schema.json",
            "metadata": {
                "type": "Report",
                "displayName": "Automotive Commercial Analytics",
                "description": "Five-page commercial and data-quality Power BI report",
            },
            "config": {
                "version": "2.0",
                "logicalId": "f0977cc4-af5a-402e-aa87-71d3493cad70",
            },
        },
    )
    _write_json(
        definition / "version.json",
        {
            "$schema": f"{REPORT_SCHEMA}/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    _write_json(
        definition / "report.json",
        {
            "$schema": f"{REPORT_SCHEMA}/report/3.1.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU06",
                    "reportVersionAtImport": {
                        "visual": "2.9.0",
                        "page": "2.1.0",
                        "report": "3.3.0",
                    },
                    "type": "SharedResources",
                }
            },
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [
                        {
                            "name": "CY24SU06",
                            "path": "BaseThemes/CY24SU06.json",
                            "type": "BaseTheme",
                        }
                    ],
                }
            ],
            "settings": {"useEnhancedTooltips": False},
        },
    )
    _write_json(
        pages_dir / "pages.json",
        {
            "$schema": f"{REPORT_SCHEMA}/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [spec["name"] for spec in PAGE_SPECS],
            "activePageName": PAGE_SPECS[0]["name"],
        },
    )
    for spec in PAGE_SPECS:
        page_dir = pages_dir / spec["name"]
        _write_json(
            page_dir / "page.json",
            {
                "$schema": f"{REPORT_SCHEMA}/page/2.1.0/schema.json",
                "name": spec["name"],
                "displayName": spec["display"],
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
            },
        )
        visuals_dir = page_dir / "visuals"
        if visuals_dir.exists():
            shutil.rmtree(visuals_dir)
        visuals = _page_visuals(spec)
        if len(visuals) != spec["visuals"]:
            raise ValueError(
                f"{spec['name']} expected {spec['visuals']} visuals, "
                f"generated {len(visuals)}"
            )
        for visual in visuals:
            _write_json(page_dir / "visuals" / visual["name"] / "visual.json", visual)


def validate_powerbi_project(path: Path = PBIP_PATH) -> dict[str, int]:
    """Validate internal cross-file references before external PBIR schema validation."""

    if not path.exists():
        raise FileNotFoundError(path)
    pages_path = REPORT_DIR / "definition" / "pages" / "pages.json"
    pages = json.loads(pages_path.read_text(encoding="utf-8"))["pageOrder"]
    visuals = list(
        (REPORT_DIR / "definition" / "pages").glob("*/visuals/*/visual.json")
    )
    model_definition = MODEL_DIR / "definition"
    table_files = list((model_definition / "tables").glob("*.tmdl"))
    measure_path = model_definition / "measures.tmdl"
    expected_visuals = sum(spec["visuals"] for spec in PAGE_SPECS)
    table_stems = {table_file.stem for table_file in table_files}
    unexpected_tables = table_stems - set(TABLES)
    desktop_auto_date_pattern = re.compile(
        r"^(?:LocalDateTable|DateTableTemplate)_[0-9a-f-]+$"
    )
    if (
        len(pages) != 5
        or len(visuals) != expected_visuals
        or not set(TABLES).issubset(table_stems)
        or any(
            desktop_auto_date_pattern.fullmatch(table_name) is None
            for table_name in unexpected_tables
        )
    ):
        raise ValueError(
            f"PBIP contract requires 5 pages, {expected_visuals} visuals, and "
            "the nine imported model tables plus only supported Desktop auto-date "
            "artifacts"
        )
    for table_name in unexpected_tables:
        auto_date_text = (
            model_definition / "tables" / f"{table_name}.tmdl"
        ).read_text(encoding="utf-8")
        if "\tisHidden\n" not in auto_date_text or not any(
            marker in auto_date_text
            for marker in ("__PBI_LocalDateTable", "__PBI_TemplateDateTable")
        ):
            raise ValueError(f"Unexpected visible model table: {table_name}")
    known_measures = {name for name, *_ in MEASURES}
    if set(MEASURE_HOME_TABLES) != known_measures:
        raise ValueError("Every measure must have exactly one declared home table")
    if not set(MEASURE_HOME_TABLES.values()).issubset(TABLES):
        raise ValueError("Measures may only use existing imported home tables")

    model_text = (model_definition / "model.tmdl").read_text(encoding="utf-8")
    database_text = (model_definition / "database.tmdl").read_text(encoding="utf-8")
    expressions_path = model_definition / "expressions.tmdl"
    expressions_text = expressions_path.read_text(encoding="utf-8")
    if (
        "\tculture: en-US" not in model_text
        or "\tsourceQueryCulture: en-US" not in model_text
        or ("\tlanguage:" in database_text and "\tlanguage: 1033" not in database_text)
    ):
        raise ValueError("Power BI model and database cultures must remain aligned")
    if re.search(r"(?m)^ref table Measures$", model_text):
        raise ValueError("The unsupported synthetic Measures table is still referenced")

    expression_declarations: dict[str, list[Path]] = {}
    expression_pattern = re.compile(
        r"(?m)^expression\s+(?:'([^']+)'|([^\s=]+))\s*="
    )
    for tmdl_path in model_definition.rglob("*.tmdl"):
        tmdl_text = tmdl_path.read_text(encoding="utf-8")
        for match in expression_pattern.finditer(tmdl_text):
            expression_name = match.group(1) or match.group(2)
            expression_declarations.setdefault(expression_name, []).append(tmdl_path)
    duplicate_expressions = {
        name: declaration_paths
        for name, declaration_paths in expression_declarations.items()
        if len(declaration_paths) != 1
    }
    if duplicate_expressions:
        raise ValueError(
            f"Named expressions must be declared exactly once: {duplicate_expressions}"
        )
    expected_expressions = {"pServer", "pDatabase"}
    if set(expression_declarations) != expected_expressions or any(
        declaration_paths != [expressions_path]
        for declaration_paths in expression_declarations.values()
    ):
        raise ValueError(
            "PostgreSQL parameters must exist only in definition/expressions.tmdl"
        )
    if (
        'expression pServer = "localhost:5432"' not in expressions_text
        or 'expression pDatabase = "automotive_analytics"' not in expressions_text
    ):
        raise ValueError("PostgreSQL parameter values changed unexpectedly")

    for table_name, spec in TABLES.items():
        table_text = (model_definition / "tables" / f"{table_name}.tmdl").read_text(
            encoding="utf-8"
        )
        if table_text.count("\n\tpartition ") != 1 or " = m\n" not in table_text:
            raise ValueError(f"{table_name} must have exactly one M partition")
        uses_parameters = (
            '#"pServer"' in table_text and '#"pDatabase"' in table_text
        )
        uses_desktop_normalized_source = re.search(
            r'PostgreSQL\.Database\("[^"@]+",\s*"automotive_analytics"',
            table_text,
        ) is not None
        if not (uses_parameters or uses_desktop_normalized_source):
            raise ValueError(
                f"{table_name} partition must use the PostgreSQL parameters or "
                "Power BI Desktop's normalized PostgreSQL source"
            )
        for column_name, (data_type, _) in spec["columns"].items():
            column_declaration = f"\tcolumn {_q(column_name)}\n"
            column_match = re.search(
                rf"(?m)^{re.escape(column_declaration)}((?:\t\t.*\n)*)",
                table_text,
            )
            if column_match is None:
                raise ValueError(f"{table_name}.{column_name} is missing")
            column_block = column_match.group(1)
            compatible_types = {data_type}
            if data_type == "decimal":
                compatible_types.add("double")
            if (
                not any(
                    f"\t\tdataType: {compatible_type}" in column_block
                    for compatible_type in compatible_types
                )
                or f"\t\tsourceColumn: {column_name}" not in column_block
            ):
                raise ValueError(
                    f"{table_name}.{column_name} has incomplete source metadata"
                )
        for column_name, calculated in CALCULATED_COLUMNS.get(table_name, {}).items():
            declaration = (
                f"\tcolumn {_q(column_name)} = {calculated['expression']}\n"
            )
            if declaration not in table_text:
                raise ValueError(f"{table_name}.{column_name} calculation is missing")
            calculated_match = re.search(
                rf"(?m)^{re.escape(declaration)}((?:\t\t.*\n)*)",
                table_text,
            )
            if (
                calculated_match is None
                or f"\t\tdataType: {calculated['data_type']}"
                not in calculated_match.group(1)
            ):
                raise ValueError(f"{table_name}.{column_name} metadata is incomplete")

    binding_errors: list[str] = []
    for visual_path in visuals:
        visual = json.loads(visual_path.read_text(encoding="utf-8"))
        query_state = visual["visual"].get("query", {}).get("queryState", {})
        for role in query_state.values():
            for projection in role.get("projections", []):
                field = projection["field"]
                if "Measure" in field:
                    measure = field["Measure"]
                    entity = measure["Expression"]["SourceRef"]["Entity"]
                    property_name = measure["Property"]
                    expected_entity = MEASURE_HOME_TABLES.get(property_name)
                    expected_query_ref = (
                        f"{expected_entity}.{property_name}"
                        if expected_entity is not None
                        else None
                    )
                    if (
                        entity != expected_entity
                        or projection["queryRef"] != expected_query_ref
                    ):
                        binding_errors.append(
                            f"{visual_path}: {entity}.{property_name}"
                        )
                if "Column" in field:
                    column = field["Column"]
                    entity = column["Expression"]["SourceRef"]["Entity"]
                    property_name = column["Property"]
                    if (
                        entity not in TABLES
                        or (
                            property_name not in TABLES[entity]["columns"]
                            and property_name
                            not in CALCULATED_COLUMNS.get(entity, {})
                        )
                    ):
                        binding_errors.append(
                            f"{visual_path}: {entity}.{property_name}"
                        )
    if binding_errors:
        raise ValueError(
            f"PBIR bindings do not resolve to TMDL objects: {binding_errors}"
        )
    dax_reference_errors: list[str] = []
    for measure_name, expression, *_ in MEASURES:
        for table_name, column_name in re.findall(
            r"'([^']+)'\[([^\]]+)\]", expression
        ):
            if table_name not in TABLES or (
                column_name not in TABLES[table_name]["columns"]
                and column_name not in CALCULATED_COLUMNS.get(table_name, {})
            ):
                dax_reference_errors.append(
                    f"{measure_name}: {table_name}.{column_name}"
                )
        for referenced_measure in re.findall(r"(?<!')\[([^\]]+)\]", expression):
            if referenced_measure not in known_measures:
                dax_reference_errors.append(
                    f"{measure_name}: [{referenced_measure}]"
                )
    if dax_reference_errors:
        raise ValueError(
            f"DAX references do not resolve to model objects: {dax_reference_errors}"
        )
    parsed_measure_homes: dict[str, str] = {}
    measure_sources = [measure_path] if measure_path.exists() else [
        model_definition / "tables" / f"{table_name}.tmdl" for table_name in TABLES
    ]
    for source in measure_sources:
        current_table: str | None = None
        for line in source.read_text(encoding="utf-8").splitlines():
            if line.startswith("table "):
                current_table = line.removeprefix("table ").strip("'")
            elif line.startswith("\tmeasure "):
                measure_name = line.removeprefix("\tmeasure ").split(
                    " = ", maxsplit=1
                )[0].strip("'")
                if measure_name in parsed_measure_homes or current_table is None:
                    raise ValueError(f"Invalid measure declaration for {measure_name}")
                parsed_measure_homes[measure_name] = current_table
    if parsed_measure_homes != MEASURE_HOME_TABLES:
        raise ValueError("Measure declarations do not match their real home tables")
    measure_count = len(parsed_measure_homes)
    if measure_count != len(MEASURES):
        raise ValueError("PBIP semantic model must retain all explicit measures")
    for measure_name, expression, *_ in MEASURES:
        home_path = (
            measure_path
            if measure_path.exists()
            else model_definition
            / "tables"
            / f"{MEASURE_HOME_TABLES[measure_name]}.tmdl"
        )
        if f"\tmeasure {_q(measure_name)} = {expression}\n" not in home_path.read_text(
            encoding="utf-8"
        ):
            raise ValueError(f"{measure_name} DAX differs from its declared expression")
    semantic_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in model_definition.rglob("*.tmdl")
    )
    if (
        re.search(r"(?m)^table Measures$", semantic_text)
        or re.search(r"(?m)^\s*partition Measures\s*=", semantic_text)
        or "Placeholder" in semantic_text
    ):
        raise ValueError("Unsupported synthetic measure-container metadata remains")
    dim_date_text = (
        model_definition / "tables" / "Dim Date.tmdl"
    ).read_text(encoding="utf-8")
    dim_date_column = re.search(
        r"(?m)^\tcolumn date\n((?:\t\t.*\n)*)", dim_date_text
    )
    if (
        "\tdataCategory: Time" not in dim_date_text
        or dim_date_column is None
        or "\t\tisKey" not in dim_date_column.group(1)
    ):
        raise ValueError("Dim Date must be marked with date as its key column")
    report_text = "\n".join(
        visual_path.read_text(encoding="utf-8") for visual_path in visuals
    )
    if any(
        token in report_text for token in ("LocalDateTable_", "DateTableTemplate_")
    ):
        raise ValueError("PBIR contains an auto-date table or hierarchy reference")
    return {
        "pages": len(pages),
        "visuals": len(visuals),
        "model_tables": len(TABLES),
        "measures": measure_count,
    }


def build_powerbi_project() -> Path:
    """Build the semantic model and report source files."""

    _build_model()
    _build_report()
    evidence = validate_powerbi_project()
    LOGGER.info(
        "Built %s (%s pages, %s visuals, %s measures)",
        PBIP_PATH,
        evidence["pages"],
        evidence["visuals"],
        evidence["measures"],
    )
    return PBIP_PATH


def main() -> None:
    """CLI entry point."""

    argparse.ArgumentParser(description=__doc__).parse_args()
    build_powerbi_project()


if __name__ == "__main__":
    main()
