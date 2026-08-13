"""Validate and load curated CSV tables into the PostgreSQL fact constellation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .config import DatabaseConfig, PROCESSED_DIR, PROCESSED_TABLES, SQL_DIR
from .data_quality import validate_processed_tables
from .utils import configure_logging, write_csv


LOGGER = configure_logging()
LOAD_ORDER = [
    "dim_date",
    "dim_customer",
    "dim_vehicle",
    "dim_dealer",
    "fact_inquiry",
    "fact_quote",
    "data_quality_metrics",
    "data_quality_issue_log",
    "quarantined_records",
    "pipeline_run_summary",
]
POSTGRES_PARAMETER_BUDGET = 50_000


def read_processed_tables(
    processed_dir: Path = PROCESSED_DIR,
) -> dict[str, pd.DataFrame]:
    """Read all curated outputs required by the database load."""

    tables: dict[str, pd.DataFrame] = {}
    for table_name in PROCESSED_TABLES:
        path = processed_dir / f"{table_name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing processed input {path}. Run `python -m src.transform` first."
            )
        tables[table_name] = pd.read_csv(
            path,
            low_memory=False,
            true_values=["True", "true", "1"],
            false_values=["False", "false", "0"],
        )
    return tables


def validate_load_inputs(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Run the same critical constraints before any database connection is opened."""

    assertions = validate_processed_tables(tables)
    LOGGER.info("Validated %s critical pre-load assertions", len(assertions))
    return assertions


def _execute_sql_file(connection: object, path: Path) -> None:
    """Execute one project SQL file through a SQLAlchemy connection."""

    sql = path.read_text(encoding="utf-8")
    connection.exec_driver_sql(sql)
    LOGGER.info("Executed %s", path.name)


def safe_chunksize(frame: pd.DataFrame) -> int:
    """Stay below PostgreSQL's bind-parameter ceiling for wide tables."""

    return max(1, POSTGRES_PARAMETER_BUDGET // max(1, len(frame.columns)))


def _prepare_for_postgres(
    table_name: str, frame: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, object] | None]:
    """Prepare database-native values that cannot be inferred safely from CSV text."""

    if table_name != "quarantined_records":
        return frame, None

    try:
        from sqlalchemy.dialects.postgresql import JSONB
    except ImportError as exc:  # pragma: no cover - guarded by loader dependency check
        raise RuntimeError(
            "PostgreSQL SQLAlchemy types are required for loading"
        ) from exc

    prepared = frame.copy()
    prepared["record_payload"] = prepared["record_payload"].map(
        lambda value: json.loads(value) if isinstance(value, str) else value
    )
    return prepared, {"record_payload": JSONB()}


def load_to_postgres(
    tables: dict[str, pd.DataFrame],
    database_config: DatabaseConfig | None = None,
    processed_dir: Path = PROCESSED_DIR,
) -> None:
    """Create database objects and transactionally replace curated table contents."""

    database_config = database_config or DatabaseConfig()

    try:
        from sqlalchemy import create_engine
    except ImportError as exc:  # pragma: no cover - depends on local database setup
        raise RuntimeError(
            "SQLAlchemy is required for database loading. Run `pip install -r requirements.txt`."
        ) from exc

    engine = create_engine(database_config.sqlalchemy_url, pool_pre_ping=True)
    summary = tables["pipeline_run_summary"].copy()
    summary["loaded_records"] = summary["clean_records"]
    summary["load_status"] = "Loaded"
    tables = {**tables, "pipeline_run_summary": summary}

    with engine.begin() as connection:
        for filename in ["01_create_schema.sql", "02_create_tables.sql"]:
            _execute_sql_file(connection, SQL_DIR / filename)
        connection.exec_driver_sql(
            "TRUNCATE TABLE "
            "automotive_analytics.fact_quote, "
            "automotive_analytics.fact_inquiry, "
            "automotive_analytics.dim_customer, "
            "automotive_analytics.dim_vehicle, "
            "automotive_analytics.dim_dealer, "
            "automotive_analytics.dim_date, "
            "automotive_analytics.data_quality_metrics, "
            "automotive_analytics.data_quality_issue_log, "
            "automotive_analytics.quarantined_records, "
            "automotive_analytics.pipeline_run_summary RESTART IDENTITY CASCADE"
        )
        for table_name in LOAD_ORDER:
            frame, dtype = _prepare_for_postgres(table_name, tables[table_name])
            frame.to_sql(
                table_name,
                connection,
                schema="automotive_analytics",
                if_exists="append",
                index=False,
                chunksize=safe_chunksize(frame),
                method="multi",
                dtype=dtype,
            )
            LOGGER.info("Loaded %-23s %9s rows", table_name, f"{len(frame):,}")
        # Creating indexes after the initial bulk insert avoids maintaining each
        # index row-by-row. Existing indexes remain idempotent on later refreshes.
        _execute_sql_file(connection, SQL_DIR / "03_create_indexes.sql")
        _execute_sql_file(connection, SQL_DIR / "04_views.sql")

    write_csv(summary, processed_dir / "pipeline_run_summary.csv")
    LOGGER.info("Database load committed and pipeline summary updated")


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate load inputs without connecting to PostgreSQL.",
    )
    args = parser.parse_args()
    tables = read_processed_tables(args.processed_dir)
    validate_load_inputs(tables)
    if args.validate_only:
        LOGGER.info("Validation-only load check complete; no database writes performed")
        return
    load_to_postgres(tables, processed_dir=args.processed_dir)


if __name__ == "__main__":
    main()
