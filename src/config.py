"""Central configuration for the analytics pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"
SQL_DIR = PROJECT_ROOT / "sql"
DOCS_DIR = PROJECT_ROOT / "docs"
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
EXCEL_DIR = PROJECT_ROOT / "excel"

RAW_TABLES = (
    "dim_customer",
    "dim_vehicle",
    "dim_dealer",
    "fact_inquiry",
    "fact_quote",
    "dim_date",
)

PROCESSED_TABLES = RAW_TABLES + (
    "data_quality_metrics",
    "data_quality_issue_log",
    "quarantined_records",
    "pipeline_run_summary",
)


@dataclass(frozen=True)
class GeneratorConfig:
    """Synthetic data generation parameters."""

    seed: int = 42
    customer_count: int = 50_000
    inquiry_count: int = 100_000
    dealer_count: int = 150
    start_date: str = "2022-01-01"
    end_date: str = "2025-12-27"


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection settings loaded from environment variables."""

    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    database: str = field(
        default_factory=lambda: os.getenv("POSTGRES_DB", "automotive_analytics")
    )
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "analytics"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))

    @property
    def sqlalchemy_url(self) -> str:
        """Return a SQLAlchemy-compatible PostgreSQL URL."""

        explicit_url = os.getenv("DATABASE_URL")
        if explicit_url:
            return explicit_url
        if not self.password:
            raise RuntimeError(
                "POSTGRES_PASSWORD is required. Copy .env.example to .env and set "
                "a private local password."
            )
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


def ensure_project_directories() -> None:
    """Create pipeline directories if they do not yet exist."""

    for directory in (
        RAW_DIR,
        PROCESSED_DIR,
        REFERENCE_DIR,
        DOCS_DIR,
        SCREENSHOTS_DIR,
        EXCEL_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
