# Power BI Project

Open [`AutomotiveCommercialAnalytics.pbip`](AutomotiveCommercialAnalytics.pbip) in Power BI Desktop. The checked-in project contains five 16:9 PBIR report pages, 59 data-bound visuals, 55 explicit DAX measures, six business relationships, and nine PostgreSQL Import-mode tables.

Power BI Desktop opens the project and refreshes all nine PostgreSQL tables. All five pages, including the 21 top KPI cards and the corrected dealer rankings, have been manually reviewed in Desktop.

## Report pages

| Page | Decision supported | Main content |
|---|---|---|
| Executive Overview | Where are volume, conversion, accepted value, and dealer contribution moving? | Five KPIs, four slicers, monthly trend, lead-source conversion, vehicle accepted value, top five dealers |
| Pricing & Competitiveness | How close are quotes to appraised value, and where is dispersion highest? | Four KPIs, vehicle comparisons, quote/market scatter, pricing detail table |
| Customer & Conversion | Which acquisition and service attributes are associated with conversion? | Four KPIs, lead-source performance, response-time bands, mileage view, detail table, evidence callout |
| Dealer Performance | Which dealers combine win rate, speed, volume, and value? | Four KPIs, volume-guarded top seven, dealer scatter, top-five accepted-value leaders, outlier table |
| Data Quality & Operations | Can the reporting evidence be trusted and reconciled? | Raw and processed quality scores, rejected and loaded record KPIs, quality checks, issue categories, record flow, run summary |

All pages use a consistent Segoe UI design, restrained navy/blue/teal status colors, business-facing labels, chart titles, tooltips, and compact slicers. The report canvas remains 1280 × 720.

## Semantic-model changes for the redesign

The six business relationships, imported tables, and PostgreSQL partitions are unchanged. The model contains 55 measures on real imported tables.

Eight measures support report-specific analysis that was not available in the original measure library:

- `Average Estimated Market Value`
- `Dealer Win Rate Top 7`
- `Dealer Accepted Value Top 5`
- `Affected Rows`
- `Raw Data Quality Rate`
- `Processed Data Quality Rate`
- `Data Quality Improvement`
- `Raw Data Quality Score`

The two dealer ranking measures were corrected to rank across both dealer ID and dealer name while retaining the external region filter. This makes the displayed Top 7 and Top 5 limits effective instead of ranking every visible dealer row as first.

Six calculated columns support monthly grain, semantic response-band ordering, and readable operational category labels:

- `Dim Date[Month Start]`
- `Fact Inquiry[Response Time Band]`
- `Fact Inquiry[Response Time Band Sort]` (hidden)
- `Data Quality Metrics[Metric Label]`
- `Data Quality Issue Log[Issue Category]`
- `Pipeline Run Summary[Pipeline Stage]`

Measures remain attached to real imported tables. There is no model table named `Measures` and no placeholder column.

The PostgreSQL parameters `pServer` and `pDatabase` are each declared once in `SemanticModel/definition/expressions.tmdl`. `model.tmdl` contains model properties and table ordering only.

## Open and refresh

1. Confirm the PostgreSQL container is healthy with `docker compose ps`.
2. Follow [`POWERBI_POSTGRESQL_CONNECTION.md`](../docs/POWERBI_POSTGRESQL_CONNECTION.md) for the host reachable from Power BI Desktop, database, credentials, expected row counts, and refresh reconciliation.
3. Open `AutomotiveCommercialAnalytics.pbip`.
4. Refresh all nine imported tables.
5. Reconcile the unfiltered KPIs, test slicer/chart interactions, inspect every tooltip and table, and check that no label is clipped at 100% zoom.
6. Compare the refreshed pages with the five genuine Desktop screenshots listed in [`screenshots/README.md`](../screenshots/README.md).

Never commit a PostgreSQL password. The report remains labelled as a synthetic portfolio scenario.

## Static validation

- Microsoft `powerbi-report-author`: offline structural validation passed with 0 errors and 0 warnings. Online validation returned 0 errors and one schema-reachability warning for Desktop's visual-container schema version 2.11.0.
- Microsoft Analysis Services `TmdlSerializer`: parsed 12 tables and 8 relationships successfully after the final Desktop save. This consists of 9 imported business tables and 6 business relationships plus Desktop's 3 hidden auto-date tables and 2 hidden date relationships.
- Repository contract: 5 pages, 59 visuals, 9 imported tables, 55 measures; every visual binding resolves to a declared model object.

Power BI Desktop runtime validation passed through manual open, PostgreSQL refresh, KPI-card review, ranking review, and inspection of all five report pages. Power BI Service deployment has not been performed.
