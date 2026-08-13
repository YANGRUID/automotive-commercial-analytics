"""Extract raw CSV files into pandas DataFrames."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import RAW_DIR, RAW_TABLES
from .utils import configure_logging, memory_mb, standardize_columns


LOGGER = configure_logging()


def extract_raw_data(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read every expected raw CSV without silently parsing business fields."""

    tables: dict[str, pd.DataFrame] = {}
    for table_name in RAW_TABLES:
        path = raw_dir / f"{table_name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing raw input {path}. Run `python -m src.generate_data` first."
            )
        frame = pd.read_csv(path, low_memory=False)
        frame = standardize_columns(frame)
        tables[table_name] = frame
        LOGGER.info(
            "Extracted %-16s rows=%9s columns=%2s memory=%7.1f MB",
            table_name,
            f"{len(frame):,}",
            len(frame.columns),
            memory_mb(frame),
        )
    return tables


def main() -> None:
    """CLI entry point that validates raw file availability and shape."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    tables = extract_raw_data(args.raw_dir)
    LOGGER.info("Extraction complete: %s raw tables", len(tables))


if __name__ == "__main__":
    main()
