"""Shared utility functions for ETL modules."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


LOGGER_NAME = "automotive_analytics"


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the project logger."""

    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def to_snake_case(value: str) -> str:
    """Convert a label to a safe lowercase snake_case column name."""

    value = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    value = re.sub(r"_{2,}", "_", value)
    return value.strip("_").lower()


def standardize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with normalized column names."""

    result = frame.copy()
    result.columns = [to_snake_case(str(column)) for column in result.columns]
    return result


def normalize_string_series(series: pd.Series, title_case: bool = False) -> pd.Series:
    """Trim whitespace and normalize empty strings in a pandas string series."""

    result = series.astype("string").str.strip().replace({"": pd.NA})
    if title_case:
        result = result.str.title()
    return result


def require_columns(
    frame: pd.DataFrame, required: Iterable[str], table_name: str
) -> None:
    """Raise a clear error when an input table is missing required columns."""

    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{table_name} is missing required columns: {missing}")


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    """Write a CSV atomically so interrupted runs do not leave partial output."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary_path, index=False)
    temporary_path.replace(path)


def memory_mb(frame: pd.DataFrame) -> float:
    """Return deep DataFrame memory usage in megabytes."""

    return float(frame.memory_usage(index=True, deep=True).sum() / 1_048_576)
