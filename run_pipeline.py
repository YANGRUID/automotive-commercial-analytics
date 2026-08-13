"""Run generation, extraction, transformation, analysis, and optional database load."""

from __future__ import annotations

import argparse
from dataclasses import replace

from src.analysis import build_analysis_artifacts
from src.config import GeneratorConfig
from src.create_excel_workbook import build_excel_workbook
from src.create_notebook import build_notebook, execute_notebook
from src.create_powerbi_project import build_powerbi_project
from src.extract import extract_raw_data
from src.generate_data import generate_dataset
from src.load import load_to_postgres, validate_load_inputs
from src.transform import transform_tables
from src.utils import configure_logging


LOGGER = configure_logging()


def main() -> None:
    """Run the deterministic end-to-end data pipeline."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-generation", action="store_true")
    parser.add_argument("--skip-notebook", action="store_true")
    parser.add_argument("--with-db", action="store_true")
    args = parser.parse_args()
    if not 0 < args.scale <= 1:
        raise ValueError("--scale must be greater than 0 and no more than 1")

    if not args.skip_generation:
        base = GeneratorConfig(seed=args.seed)
        config = replace(
            base,
            customer_count=max(500, int(base.customer_count * args.scale)),
            inquiry_count=max(1_000, int(base.inquiry_count * args.scale)),
        )
        generate_dataset(config)
    raw_tables = extract_raw_data()
    processed_tables = transform_tables(raw_tables)
    validate_load_inputs(processed_tables)
    build_analysis_artifacts()
    build_excel_workbook()
    build_powerbi_project()
    if not args.skip_notebook:
        notebook_path = build_notebook()
        execute_notebook(notebook_path)
    if args.with_db:
        load_to_postgres(processed_tables)
    else:
        LOGGER.info(
            "Database load skipped. Re-run with --with-db after starting PostgreSQL."
        )
    LOGGER.info("Pipeline complete")


if __name__ == "__main__":
    main()
