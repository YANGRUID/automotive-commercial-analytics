# Power Query Design

## Responsibility boundary

Python owns reproducible generation, deduplication, business-rule validation, corrections, quarantine, and derived analytical columns. PostgreSQL owns types, constraints, referential integrity, indexes, and reusable analytical views. Power Query should remain a thin semantic-import layer: connect, select approved tables/views, enforce display types, rename for readability, and create only BI-specific helper tables.

Repeating the ETL logic in Power Query would create two competing definitions and make reconciliation harder.

## Parameters

The checked-in semantic model uses two text parameters:

| Parameter | Example | Purpose |
|---|---|---|
| `pServer` | `localhost:5432` | PostgreSQL endpoint |
| `pDatabase` | `automotive_analytics` | Database name |

The approved reporting schema is fixed as `automotive_analytics` in each table partition rather than exposed as a third model parameter.

Credentials are configured in Power BI's data-source settings and are never stored in M code.

## Source query pattern

```powerquery
let
    Source = PostgreSQL.Database(pServer, pDatabase, [CreateNavigationProperties=false]),
    FactInquiryRaw = Source{[Schema="automotive_analytics", Item="fact_inquiry"]}[Data],
    SelectedColumns = Table.SelectColumns(
        FactInquiryRaw,
        {
            "inquiry_id", "customer_id", "vehicle_id", "inquiry_date",
            "lead_source", "status", "final_sale_price", "winning_dealer_id",
            "conversion_flag", "days_to_conversion", "quote_count",
            "highest_quote", "lowest_quote", "average_quote",
            "fastest_response_hours", "quote_spread", "quote_spread_pct",
            "vehicle_age_at_inquiry"
        }
    ),
    TypedColumns = Table.TransformColumnTypes(
        SelectedColumns,
        {
            {"inquiry_id", type text}, {"customer_id", type text},
            {"vehicle_id", type text}, {"inquiry_date", type date},
            {"lead_source", type text}, {"status", type text},
            {"final_sale_price", Currency.Type}, {"winning_dealer_id", type text},
            {"conversion_flag", type logical}, {"days_to_conversion", Int64.Type},
            {"quote_count", Int64.Type}, {"highest_quote", Currency.Type},
            {"lowest_quote", Currency.Type}, {"average_quote", Currency.Type},
            {"fastest_response_hours", type number}, {"quote_spread", Currency.Type},
            {"quote_spread_pct", Percentage.Type}, {"vehicle_age_at_inquiry", Int64.Type}
        },
        "en-US"
    )
in
    TypedColumns
```

Use the same source/navigation pattern for each approved table. Keep query folding intact by selecting and typing columns before any non-foldable step.

## Query-specific steps

Use these exact model/query names so the supplied DAX and PBIR bindings resolve:

| PostgreSQL object | Power BI table |
|---|---|
| `dim_date` | `Dim Date` |
| `dim_customer` | `Dim Customer` |
| `dim_vehicle` | `Dim Vehicle` |
| `dim_dealer` | `Dim Dealer` |
| `fact_inquiry` | `Fact Inquiry` |
| `fact_quote` | `Fact Quote` |
| `data_quality_metrics` | `Data Quality Metrics` |
| `data_quality_issue_log` | `Data Quality Issue Log` |
| `quarantined_records` | `Quarantined Records` |
| `pipeline_run_summary` | `Pipeline Run Summary` |

The checked-in PBIP already applies these names in TMDL. The mapping remains here for anyone rebuilding the model through the Power Query UI.

### Dimensions

- Trim dimension labels only as a defensive presentation step; the Python layer has already normalized them.
- Set key columns to Text so leading zeros are preserved.
- Set `estimated_market_value` and `dealer_rating` to Decimal/Currency as applicable.
- Keep explicit `Unknown` members; do not convert them back to null.
- For `Dim Date`, set Date, Whole Number, Text, and Logical types; do not generate an automatic date table.

### Facts

- Keep `Fact Inquiry` at one row per `inquiry_id` and `Fact Quote` at one row per `quote_id`.
- Do not merge quote rows into inquiry rows in Power Query; that would multiply inquiry-level conversion and value measures.
- Preserve logical flags as Boolean.
- Preserve `quote_to_market_ratio` and `quote_spread_pct` as Decimal Numbers whose 0–1 scale is formatted as Percentage in the model.
- Do not recalculate rankings, spreads, response imputation, or anomaly flags in Power Query.

### Quality and operations

- Load `data_quality_metrics`, `data_quality_issue_log`, `quarantined_records`, and `pipeline_run_summary` as separate operational tables.
- Disable load for `quarantined_records[record_payload]` if the detailed JSON is not used in the report; keep record ID, table, issue type, action, and detected timestamp.
- Restrict detailed quarantine access if the project is adapted to real customer data.

## Measure organisation

The source generator can emit measures together in `SemanticModel/definition/measures.tmdl` through TMDL partial declarations; Power BI Desktop may consolidate them into the real table files when it saves the project. Each measure belongs to an imported table: inquiry and conversion measures to `Fact Inquiry`, quote and pricing measures to `Fact Quote`, dealer measures to `Dim Dealer`, metric-quality measures to `Data Quality Metrics`, issue counts to `Data Quality Issue Log`, and load-control measures to `Pipeline Run Summary`. No disconnected or calculated storage table is required.

## Refresh and gateway

1. Test local refresh against the Docker PostgreSQL service.
2. In Power BI Service, configure an on-premises gateway or a managed PostgreSQL endpoint.
3. Map `pServer` and `pDatabase` to environment-specific values.
4. Schedule refresh only after the Python/SQL pipeline has completed successfully.
5. Use the Data Quality & Operations page as the first post-refresh control.

## Validation after refresh

- `Total Inquiries` must equal the curated `fact_inquiry` row count.
- `Total Quotes` must equal the curated `fact_quote` row count.
- `Converted Inquiries` must equal the count of inquiries with `conversion_flag = TRUE`.
- `Total Accepted Quote Value` must reconcile to total inquiry `final_sale_price` within CHF 0.01.
- Every filter should reduce, not multiply, fact rows.
