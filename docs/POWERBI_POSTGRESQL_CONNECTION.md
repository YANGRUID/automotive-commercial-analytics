# Power BI PostgreSQL Connection

## Validated local endpoint

The checked-in PBIP uses PostgreSQL Import mode as its primary data source. Each imported TMDL partition calls `PostgreSQL.Database` and navigates to a table in the `automotive_analytics` schema; no imported table uses `Csv.Document` or `File.Contents`.

| Setting | Value |
|---|---|
| Docker host endpoint | `localhost:5432` |
| Current Power BI Desktop endpoint | `10.211.55.2:5432` |
| Port | `5432` |
| Generator `pServer` default | `localhost:5432` |
| Database | `automotive_analytics` |
| Schema | `automotive_analytics` |
| Connection mode | Import |
| Authentication | Database |
| Username | `analytics` |
| Password | Enter the local `POSTGRES_PASSWORD` that initialized the Docker volume. It is not stored in the PBIP or this document. |

The checked-in Desktop-normalized partitions currently use `10.211.55.2:5432`, the Docker host address reachable from the Windows virtual machine used for the manual Power BI test. If that address changes, update the data source in Power BI Desktop to the new host-reachable address; keep port `5432` and database `automotive_analytics`. The source generator retains `localhost:5432` as its portable same-machine default.

## Tables Power BI loads

The semantic model imports these nine base tables. The row counts were reconciled between PostgreSQL and the curated CSVs on 2026-08-11.

| PostgreSQL table | Power BI table | Expected rows |
|---|---|---:|
| `automotive_analytics.dim_date` | `Dim Date` | 1,461 |
| `automotive_analytics.dim_customer` | `Dim Customer` | 50,000 |
| `automotive_analytics.dim_vehicle` | `Dim Vehicle` | 99,923 |
| `automotive_analytics.dim_dealer` | `Dim Dealer` | 150 |
| `automotive_analytics.fact_inquiry` | `Fact Inquiry` | 99,813 |
| `automotive_analytics.fact_quote` | `Fact Quote` | 343,120 |
| `automotive_analytics.data_quality_metrics` | `Data Quality Metrics` | 10 |
| `automotive_analytics.data_quality_issue_log` | `Data Quality Issue Log` | 18 |
| `automotive_analytics.pipeline_run_summary` | `Pipeline Run Summary` | 6 |

Do not add the SQL views to the current semantic model. The five views are live and queryable, but the report is already bound to the base-table model above. `quarantined_records` is also intentionally excluded from the PBIP because its detailed JSON payload is not required by the checked-in report pages.

## Relationship validation

After refresh, confirm these six relationships. All filters are single direction. The quote-date relationship stays inactive so it does not create an ambiguous date path.

| From | To | Cardinality | Active |
|---|---|---|---|
| `Fact Inquiry[inquiry_date]` | `Dim Date[date]` | Many-to-one | Yes |
| `Fact Inquiry[customer_id]` | `Dim Customer[customer_id]` | Many-to-one | Yes |
| `Fact Inquiry[vehicle_id]` | `Dim Vehicle[vehicle_id]` | Many-to-one | Yes |
| `Fact Quote[inquiry_id]` | `Fact Inquiry[inquiry_id]` | Many-to-one | Yes |
| `Fact Quote[dealer_id]` | `Dim Dealer[dealer_id]` | Many-to-one | Yes |
| `Fact Quote[quote_date]` | `Dim Date[date]` | Many-to-one | No |

The `Total Quotes by Quote Date` measure activates the inactive quote-date relationship with `USERELATIONSHIP` and disables only the competing Date → Inquiry filter for that calculation.

## Refresh procedure

1. In the repository root, confirm PostgreSQL is available:

   ```bash
   docker compose ps
   ```

   The `postgres` service must show `healthy`.

2. If the curated data has changed, reload it before opening Power BI:

   ```bash
   python run_pipeline.py --skip-generation --skip-notebook --with-db
   ```

3. Open `powerbi/AutomotiveCommercialAnalytics.pbip` in Power BI Desktop.
4. Open **File → Options and settings → Data source settings** and confirm the PostgreSQL source is `10.211.55.2:5432` with database `automotive_analytics`. If the Windows VM can no longer reach that address, replace it with the current host address.
5. Select **Refresh**. When prompted, choose **Database** authentication and enter:
   - Username: `analytics`
   - Password: the local `POSTGRES_PASSWORD` used by Docker Compose
6. Apply credentials at the server/database data-source level. Do not place the password in M, TMDL, `.env.example`, screenshots, or documentation.
7. Confirm the nine imported business tables appear in the model. There must not be a table named `Measures`; all 55 measures are attached to real tables.
8. Confirm the six relationships match the table above and that `Quote Date` remains inactive.

For this local development database, Power BI Desktop may ask whether to continue without an encrypted connection. Only accept an unencrypted connection for this local Docker endpoint; use TLS for any remote or shared database.

## Post-refresh reconciliation

Before accepting the Desktop refresh, verify these unfiltered measures:

| Measure | Expected result |
|---|---:|
| Total Inquiries | 99,813 |
| Total Quotes | 343,120 |
| Converted Inquiries | 32,464 |
| Total Accepted Quote Value | CHF 695,085,974.67 |

Also confirm that:

- converted inquiries equal accepted quotes: 32,464 on each fact;
- inquiry `final_sale_price` equals accepted quote value to CHF 0.01;
- filters reduce rows rather than multiplying them;
- all five report pages render without missing fields or visual errors;
- the Data Quality & Operations page shows the pipeline rows as `Loaded`.

## Validation status

The PostgreSQL service, schema, load, row counts, views, indexes, constraints, 24 analytics queries, and 10 database-quality queries passed live validation on 2026-08-11. The PBIP source and bindings pass repository checks, Microsoft PBIR validation, and TMDL parsing.

The earlier generated PBIP used `en-CH` for `Model.Culture` and `Model.SourceQueryCulture`; Power BI Desktop resolved both to LCID 4096 and rejected the project. Both properties now use `en-US`. The project subsequently opened, refreshed from PostgreSQL, and rendered all five pages in Desktop. The 21 top KPI cards and the corrected dealer rankings were included in the final manual review.
