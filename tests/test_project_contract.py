"""Repository-level checks for analytical completeness and handoff integrity."""

from __future__ import annotations

import json
import re
from pathlib import Path

import nbformat
import pandas as pd
from pglast import parse_sql

from src.config import DatabaseConfig
from src.create_excel_workbook import validate_excel_workbook
from src.create_powerbi_project import (
    CALCULATED_COLUMNS,
    MEASURE_HOME_TABLES,
    MEASURES_BY_HOME_TABLE,
    TABLES,
    validate_powerbi_project,
)
from src.load import safe_chunksize


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_postgresql_files_parse_and_analysis_query_count() -> None:
    sql_files = sorted((PROJECT_ROOT / "sql").glob("*.sql"))
    assert len(sql_files) == 6
    for path in sql_files:
        assert parse_sql(path.read_text(encoding="utf-8")), path

    analysis_sql = (PROJECT_ROOT / "sql" / "05_analysis_queries.sql").read_text(
        encoding="utf-8"
    )
    numbered_queries = re.findall(r"^--\s+\d{2}\.", analysis_sql, flags=re.MULTILINE)
    assert len(numbered_queries) >= 20

    indexes = (PROJECT_ROOT / "sql" / "03_create_indexes.sql").read_text(
        encoding="utf-8"
    )
    assert (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_quote_one_accepted_per_inquiry"
        in indexes
    )


def test_loader_chunk_size_respects_postgresql_parameter_budget() -> None:
    wide_frame = pd.DataFrame(columns=[f"c{i}" for i in range(18)])
    chunk_size = safe_chunksize(wide_frame)
    assert chunk_size * len(wide_frame.columns) <= 50_000


def test_database_config_reads_environment_at_instantiation(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "database.internal")
    monkeypatch.setenv("POSTGRES_PORT", "5544")
    monkeypatch.setenv("POSTGRES_PASSWORD", "unit-test-placeholder")
    config = DatabaseConfig()
    assert config.host == "database.internal"
    assert config.port == 5544
    assert "database.internal:5544" in config.sqlalchemy_url


def test_required_dax_measures_are_defined() -> None:
    dax = (PROJECT_ROOT / "powerbi" / "dax_measures.md").read_text(encoding="utf-8")
    required = [
        "Total Inquiries",
        "Total Quotes",
        "Converted Inquiries",
        "Conversion Rate",
        "Average Quote",
        "Maximum Quote",
        "Minimum Quote",
        "Average Quote Spread",
        "Average Sale Value",
        "Average Response Time",
        "Average Quotes per Inquiry",
        "Dealer Win Rate",
        "Quote-to-Market Ratio",
        "Month-over-Month Inquiry Growth",
        "Year-over-Year Inquiry Growth",
        "Previous Month Conversion Rate",
        "Conversion Rate Change",
        "Total Accepted Quote Value",
        "Average Days to Conversion",
        "Dealer Rank",
        "Active Dealers",
        "Raw Data Quality Score",
        "Data Quality Score",
        "Completeness Rate",
        "Validity Rate",
        "Uniqueness Rate",
        "Referential Integrity Rate",
    ]
    for measure in required:
        assert re.search(
            rf"^{re.escape(measure)}\s*=", dax, flags=re.MULTILINE
        ), measure
    assert (
        len(re.findall(r"^[A-Za-z0-9][A-Za-z0-9 %\-]+\s*=", dax, flags=re.MULTILINE))
        >= 25
    )
    assert "CROSSFILTER ( 'Dim Date'[date], 'Fact Inquiry'[inquiry_date], NONE )" in dax


def test_markdown_local_links_resolve() -> None:
    link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    failures: list[str] = []
    for markdown_path in PROJECT_ROOT.rglob("*.md"):
        content = markdown_path.read_text(encoding="utf-8")
        for target in link_pattern.findall(content):
            target = target.strip().strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative_target = target.split("#", maxsplit=1)[0]
            if not relative_target:
                continue
            if not (markdown_path.parent / relative_target).resolve().exists():
                failures.append(
                    f"{markdown_path.relative_to(PROJECT_ROOT)} -> {target}"
                )
    assert not failures, failures


def test_full_scale_generated_dataset_and_summary() -> None:
    def csv_rows(path: Path) -> int:
        with path.open("rb") as handle:
            return max(0, sum(1 for _ in handle) - 1)

    raw = PROJECT_ROOT / "data" / "raw"
    processed = PROJECT_ROOT / "data" / "processed"
    assert csv_rows(raw / "dim_customer.csv") >= 50_000
    assert csv_rows(raw / "fact_inquiry.csv") >= 100_000
    assert 250_000 <= csv_rows(raw / "fact_quote.csv") <= 400_000
    assert 100 <= csv_rows(processed / "dim_dealer.csv") <= 200

    summary = json.loads(
        (processed / "analysis_summary.json").read_text(encoding="utf-8")
    )
    assert summary["kpis"]["total_inquiries"] == csv_rows(
        processed / "fact_inquiry.csv"
    )
    assert summary["kpis"]["total_quotes"] == csv_rows(processed / "fact_quote.csv")
    assert 0 <= summary["kpis"]["conversion_rate"] <= 1
    assert summary["kpis"]["processed_data_quality_score"] == 1


def test_notebook_is_executed_without_error_outputs() -> None:
    path = PROJECT_ROOT / "notebooks" / "exploratory_analysis.ipynb"
    notebook = nbformat.read(path, as_version=4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    assert code_cells
    assert all(cell.get("execution_count") is not None for cell in code_cells)
    error_outputs = [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    assert not error_outputs


def test_excel_workbook_is_formula_driven_and_inspectable() -> None:
    evidence = validate_excel_workbook(
        PROJECT_ROOT / "excel" / "automotive_commercial_analysis.xlsx"
    )
    assert evidence["sheets"] >= 7
    assert evidence["formulas"] >= 50
    assert evidence["charts"] >= 3


def test_powerbi_project_contains_bound_report_and_semantic_model() -> None:
    evidence = validate_powerbi_project(
        PROJECT_ROOT / "powerbi" / "AutomotiveCommercialAnalytics.pbip"
    )
    assert evidence == {
        "pages": 5,
        "visuals": 59,
        "model_tables": 9,
        "measures": 55,
    }


def test_powerbi_import_tables_use_postgresql_as_the_primary_source() -> None:
    model_dir = (
        PROJECT_ROOT
        / "powerbi"
        / "AutomotiveCommercialAnalytics.SemanticModel"
        / "definition"
    )
    model = (model_dir / "model.tmdl").read_text(encoding="utf-8")
    database = (model_dir / "database.tmdl").read_text(encoding="utf-8")
    expressions = (model_dir / "expressions.tmdl").read_text(encoding="utf-8")
    assert "\tculture: en-US" in model
    assert "\tsourceQueryCulture: en-US" in model
    assert "\tlanguage:" not in database or "\tlanguage: 1033" in database
    assert "en-CH" not in model
    assert "expression pServer" not in model
    assert "expression pDatabase" not in model
    assert expressions.count('expression pServer = "localhost:5432"') == 1
    assert expressions.count('expression pDatabase = "automotive_analytics"') == 1

    table_files = set((model_dir / "tables").glob("*.tmdl"))
    table_stems = {path.stem for path in table_files}
    assert set(TABLES).issubset(table_stems)
    auto_date_tables = table_stems - set(TABLES)
    assert len(auto_date_tables) == 3
    assert all(
        re.fullmatch(r"(?:LocalDateTable|DateTableTemplate)_[0-9a-f-]+", name)
        for name in auto_date_tables
    )
    semantic_text = "\n".join(
        path.read_text(encoding="utf-8") for path in model_dir.rglob("*.tmdl")
    )
    assert semantic_text.count("annotation __PBI_LocalDateTable = true") == 2
    assert semantic_text.count("annotation __PBI_TemplateDateTable = true") == 1
    for table_name in auto_date_tables:
        auto_date_text = (
            model_dir / "tables" / f"{table_name}.tmdl"
        ).read_text(encoding="utf-8")
        assert "\tisHidden\n" in auto_date_text

    dim_date = (model_dir / "tables" / "Dim Date.tmdl").read_text(
        encoding="utf-8"
    )
    assert "\tdataCategory: Time" in dim_date
    date_column = re.search(r"(?m)^\tcolumn date\n((?:\t\t.*\n)*)", dim_date)
    assert date_column is not None
    assert "\t\tisKey" in date_column.group(1)

    expression_declarations: dict[str, list[Path]] = {}
    expression_pattern = re.compile(
        r"(?m)^expression\s+(?:'([^']+)'|([^\s=]+))\s*="
    )
    for tmdl_path in model_dir.rglob("*.tmdl"):
        for match in expression_pattern.finditer(
            tmdl_path.read_text(encoding="utf-8")
        ):
            expression_name = match.group(1) or match.group(2)
            expression_declarations.setdefault(expression_name, []).append(tmdl_path)
    assert set(expression_declarations) == {"pServer", "pDatabase"}
    assert all(
        declaration_paths == [model_dir / "expressions.tmdl"]
        for declaration_paths in expression_declarations.values()
    )

    import_tables = [
        model_dir / "tables" / f"{table_name}.tmdl" for table_name in TABLES
    ]
    assert len(import_tables) == 9
    for path in import_tables:
        source = path.read_text(encoding="utf-8")
        assert "PostgreSQL.Database(" in source, path
        assert 'Schema="automotive_analytics"' in source, path
        assert (
            source.count('#"pServer"') == 1
            and source.count('#"pDatabase"') == 1
        ) or re.search(
            r'PostgreSQL\.Database\("[^"@]+",\s*"automotive_analytics"',
            source,
        ), path
        assert "Csv.Document" not in source, path
        assert "File.Contents" not in source, path


def test_powerbi_uses_one_explicit_date_dimension() -> None:
    processed = PROJECT_ROOT / "data" / "processed"
    dates = pd.to_datetime(pd.read_csv(processed / "dim_date.csv")["date"])
    assert not dates.isna().any()
    assert dates.is_unique
    assert dates.min() == pd.Timestamp("2022-01-01")
    assert dates.max() == pd.Timestamp("2025-12-31")
    assert dates.tolist() == pd.date_range(dates.min(), dates.max()).tolist()

    for file_name, column_name in (
        ("fact_inquiry.csv", "inquiry_date"),
        ("fact_quote.csv", "quote_date"),
    ):
        fact_dates = pd.to_datetime(
            pd.read_csv(processed / file_name, usecols=[column_name])[column_name]
        )
        assert fact_dates.between(dates.min(), dates.max()).all()

    model_dir = (
        PROJECT_ROOT
        / "powerbi"
        / "AutomotiveCommercialAnalytics.SemanticModel"
        / "definition"
    )
    relationships = (model_dir / "relationships.tmdl").read_text(encoding="utf-8")
    assert relationships.count("relationship ") == 8
    assert "relationship 'Inquiry Date'\n" in relationships
    assert "\tfromColumn: 'Fact Inquiry'.inquiry_date\n" in relationships
    assert "\ttoColumn: 'Dim Date'.date\n" in relationships
    quote_date = relationships.split("relationship 'Quote Date'\n", maxsplit=1)[1]
    assert quote_date.startswith(
        "\tisActive: false\n"
        "\tfromColumn: 'Fact Quote'.quote_date\n"
        "\ttoColumn: 'Dim Date'.date\n"
    )
    assert "Data Quality Metrics'.assessment_date" in relationships
    assert "Pipeline Run Summary" not in relationships


def test_powerbi_measures_use_partial_real_table_declarations() -> None:
    model_dir = (
        PROJECT_ROOT
        / "powerbi"
        / "AutomotiveCommercialAnalytics.SemanticModel"
        / "definition"
    )
    measure_path = model_dir / "measures.tmdl"
    model = (model_dir / "model.tmdl").read_text(encoding="utf-8")
    assert not (model_dir / "tables" / "Measures.tmdl").exists()
    assert "ref table Measures" not in model
    assert set(MEASURE_HOME_TABLES.values()) == set(MEASURES_BY_HOME_TABLE)
    assert len(MEASURE_HOME_TABLES) == 55
    for home_table, measure_names in MEASURES_BY_HOME_TABLE.items():
        source_path = (
            measure_path
            if measure_path.exists()
            else model_dir / "tables" / f"{home_table}.tmdl"
        )
        measures = source_path.read_text(encoding="utf-8")
        assert f"table '{home_table}'" in measures
        assert "table Measures" not in measures
        assert "Placeholder" not in measures
        for measure_name in measure_names:
            assert f"\tmeasure '{measure_name}' =" in measures

    calculated_count = 0
    for table_name, columns in CALCULATED_COLUMNS.items():
        table_text = (model_dir / "tables" / f"{table_name}.tmdl").read_text(
            encoding="utf-8"
        )
        for column_name in columns:
            assert f"\tcolumn '{column_name}' =" in table_text
            calculated_count += 1
    assert calculated_count == 6

    report_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            PROJECT_ROOT
            / "powerbi"
            / "AutomotiveCommercialAnalytics.Report"
            / "definition"
        ).rglob("*.json")
    )
    assert '"Entity": "Measures"' not in report_text
    assert '"queryRef": "Measures.' not in report_text
    assert "LocalDateTable_" not in report_text
    assert "DateTableTemplate_" not in report_text
    assert "Date Hierarchy" not in report_text


def test_powerbi_final_visual_polish_contract() -> None:
    report_pages = (
        PROJECT_ROOT
        / "powerbi"
        / "AutomotiveCommercialAnalytics.Report"
        / "definition"
        / "pages"
    )
    page_card_counts = {
        "ExecutiveOverview": 5,
        "PricingCompetitiveness": 4,
        "CustomerConversion": 4,
        "DealerPerformance": 4,
        "DataQualityOperations": 4,
    }
    expected_card_measures = {
        "ExecutiveOverview": {
            "Total Inquiries",
            "Conversion Rate",
            "Total Accepted Quote Value",
            "Average Response Time",
            "Active Dealers",
        },
        "PricingCompetitiveness": {
            "Average Estimated Market Value",
            "Average Quote",
            "Quote-to-Market Ratio",
            "Average Quote Spread",
        },
        "CustomerConversion": {
            "Total Inquiries",
            "Converted Inquiries",
            "Conversion Rate",
            "Average Fastest Response Time",
        },
        "DealerPerformance": {
            "Total Quotes",
            "Dealer Wins",
            "Dealer Win Rate",
            "Average Response Time",
        },
        "DataQualityOperations": {
            "Raw Data Quality Score",
            "Data Quality Score",
            "Rejected Records",
            "Loaded Records",
        },
    }
    visual_payloads: dict[str, list[dict[str, object]]] = {}
    presentation_labels: list[str] = []
    for page_name, expected_cards in page_card_counts.items():
        payloads = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (report_pages / page_name / "visuals").glob(
                "*/visual.json"
            )
        ]
        visual_payloads[page_name] = payloads
        cards = [
            payload
            for payload in payloads
            if payload["visual"]["visualType"] == "card"
        ]
        assert len(cards) == expected_cards
        assert all(
            len(
                card["visual"]["query"]["queryState"]["Values"][
                    "projections"
                ]
            )
            == 1
            for card in cards
        )
        card_measures = {
            card["visual"]["query"]["queryState"]["Values"]["projections"][0][
                "field"
            ]["Measure"]["Property"]
            for card in cards
        }
        assert card_measures == expected_card_measures[page_name]
        for card in cards:
            objects = card["visual"]["objects"]
            assert objects["labels"][0]["properties"]["fontSize"] == {
                "expr": {"Literal": {"Value": "35D"}}
            }
            padding = card["visual"]["visualContainerObjects"]["padding"][0][
                "properties"
            ]
            assert all(
                padding[side] == {"expr": {"Literal": {"Value": "4D"}}}
                for side in ("top", "bottom", "left", "right")
            )
        for payload in payloads:
            for role in (
                payload["visual"].get("query", {}).get("queryState", {}).values()
            ):
                presentation_labels.extend(
                    projection["nativeQueryRef"]
                    for projection in role.get("projections", [])
                )

    assert not [
        label
        for label in presentation_labels
        if re.search(r"(?<![A-Za-z0-9])[a-z][a-z0-9]*_[a-z0-9_]+", label)
    ]
    assert not [
        label
        for label in presentation_labels
        if label.endswith(("...", "…"))
    ]

    report_text = json.dumps(visual_payloads, ensure_ascii=False)
    assert "Quote-to-market ratio by dealer region" in report_text
    assert '"Property": "dealer_region"' in report_text
    assert "Market value vs average quote by brand and vehicle type" in report_text
    assert '"nativeQueryRef": "Vehicle Type"' in report_text
    assert "Market Value (CHF)" in report_text
    assert "Average Quote (CHF)" in report_text
    assert "Raw-to-processed data quality improvement" in report_text
    assert '"Property": "Raw Data Quality Rate"' in report_text
    assert '"Property": "Processed Data Quality Rate"' in report_text
    assert '"Property": "Data Quality Improvement"' in report_text
    assert '"FillRule"' in report_text
    assert "Faster responses are associated with higher conversion" in report_text
    assert "a 3.84 percentage-point gap" in report_text
    assert "Top 7 dealers by win rate (250+ quotes)" in report_text
    assert "Top 10 dealers by win rate" not in report_text
    assert "Top 5 dealers by accepted value (250+ quotes)" in report_text
    assert '"Property": "Dealer Win Rate Top 7"' in report_text
    assert "Load Status" in report_text
    assert "Dealer Rating" in report_text
    assert 'CHF #,##0.0,,\\"M\\"' in report_text
    assert 'CHF #,##0.0,\\"K\\"' in report_text


def test_powerbi_pricing_and_response_insights_recompute() -> None:
    processed = PROJECT_ROOT / "data" / "processed"
    inquiries = pd.read_csv(processed / "fact_inquiry.csv")
    quotes = pd.read_csv(processed / "fact_quote.csv")
    dealers = pd.read_csv(processed / "dim_dealer.csv")

    joined_quotes = quotes.merge(
        dealers[["dealer_id", "dealer_region"]],
        on="dealer_id",
        validate="many_to_one",
    )
    regional = joined_quotes.groupby("dealer_region").agg(
        quote_value=("quote_amount", "sum"),
        market_value=("estimated_market_value", "sum"),
    )
    regional["ratio"] = regional["quote_value"] / regional["market_value"]
    assert regional["ratio"].between(0.91, 0.93).all()
    assert regional["ratio"].max() - regional["ratio"].min() < 0.012

    measure_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            PROJECT_ROOT
            / "powerbi"
            / "AutomotiveCommercialAnalytics.SemanticModel"
            / "definition"
            / "tables"
        ).glob("*.tmdl")
    )
    assert (
        "DIVIDE ( SUM ( 'Fact Quote'[quote_amount] ), "
        "SUM ( 'Fact Quote'[estimated_market_value] ) )"
    ) in measure_source

    under_eight = inquiries["fastest_response_hours"] < 8
    fast_rate = inquiries.loc[under_eight, "conversion_flag"].mean()
    slower_rate = inquiries.loc[~under_eight, "conversion_flag"].mean()
    assert round(fast_rate * 100, 2) == 33.27
    assert round(slower_rate * 100, 2) == 29.43
    assert round((fast_rate - slower_rate) * 100, 2) == 3.84


def test_powerbi_dealer_rankings_have_exact_visible_limits() -> None:
    measures = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            PROJECT_ROOT
            / "powerbi"
            / "AutomotiveCommercialAnalytics.SemanticModel"
            / "definition"
            / "tables"
        ).glob("*.tmdl")
    )
    assert "ALLSELECTED ( 'Dim Dealer'[dealer_id], 'Dim Dealer'[dealer_name] )" in measures
    assert "measure 'Dealer Win Rate Top 7'" in measures
    assert "[Dealer Rank] <= 7" in measures
    assert "Dealer Win Rate Top 10" not in measures

    processed = PROJECT_ROOT / "data" / "processed"
    quotes = pd.read_csv(processed / "fact_quote.csv")
    dealer_stats = quotes.groupby("dealer_id").agg(
        quotes=("quote_id", "nunique"),
        wins=("accepted_flag", "sum"),
        accepted_value=(
            "quote_amount",
            lambda values: values[quotes.loc[values.index, "accepted_flag"]].sum(),
        ),
    )
    eligible = dealer_stats[dealer_stats["quotes"] >= 250].copy()
    eligible["win_rate"] = eligible["wins"] / eligible["quotes"]
    seventh = eligible.nlargest(7, "win_rate")["win_rate"].min()
    fifth = eligible.nlargest(5, "accepted_value")["accepted_value"].min()
    assert (eligible["win_rate"] >= seventh).sum() == 7
    assert (eligible["accepted_value"] >= fifth).sum() == 5


def test_insights_are_traceable_to_exact_evidence() -> None:
    summary = json.loads(
        (PROJECT_ROOT / "data" / "processed" / "analysis_summary.json").read_text(
            encoding="utf-8"
        )
    )
    insights = (PROJECT_ROOT / "docs" / "business_insights.md").read_text(
        encoding="utf-8"
    )
    assert f"{summary['kpis']['total_inquiries']:,}" in insights
    assert f"{summary['kpis']['total_quotes']:,}" in insights
    assert f"{summary['kpis']['quote_anomalies']:,}" in insights
    assert (
        f"{summary['evidence']['dealer_referral_lift_pp_vs_social']:.2f} percentage points"
        in insights
    )
