# Interview Walkthrough

## Tell me about this project.

I built an analytics case study for a fictional Swiss automotive quotation marketplace. A customer submits a vehicle sale inquiry, several dealers quote, and one quote may be accepted. I generated four years of reproducible synthetic data, introduced controlled raw-data defects, built a Python/Pandas ETL and PostgreSQL fact constellation, wrote 24 analytical SQL queries, created a source-controlled five-page Power BI Project with 55 measures and 59 bound visuals, generated an Excel decision workbook, executed an exploratory notebook, and translated the results into management actions.

## What business problem were you solving?

Management needed to know whether demand and conversion were improving, which dealers were competitive and fast, how quotation spread varied by vehicle, which acquisition channels produced quality inquiries, and whether the evidence was reliable. The model supports commercial and operational decisions without mixing inquiry conversion with dealer quote win rate.

## Why did you use a fact constellation?

A fact constellation gives predictable filters while representing both business grains honestly. Dimensions hold customer, vehicle, dealer, and date attributes. The inquiry fact is one row per inquiry; the quote fact is one row per dealer response. I connect inquiry to quote as a 1-to-many header/line relationship because a dealer quote cannot exist without an inquiry. Calling it a constellation is more precise than calling it a pure star and avoids a flattened table that would duplicate inquiry measures.

## Why Power BI?

The target BI analyst roles value governed self-service reporting, DAX, Power Query, and stakeholder communication. The repository includes a real PBIP with an editable TMDL semantic model, five PBIR pages, 59 bound visuals, and 55 measures. Microsoft's PBIR validator and TMDL parser pass, and the PostgreSQL-backed report has been opened, refreshed, and manually reviewed in Power BI Desktop.

## What did Python do?

Python generated synthetic data with seed 42, including depreciation, mileage, brand value, dealer competitiveness, response time, seasonality, and conversion relationships. Pandas extracted CSVs, standardized schema and text, parsed types, repaired defensible issues, quarantined invalid rows, reconciled accepted quotes, calculated derived columns, persisted quality evidence, and built and executed the notebook.

## What did SQL do?

PostgreSQL enforces keys, ranges, and conversion consistency; indexes the main date and join paths; and exposes reusable inquiry, quote, dealer, monthly, and quality views. The 24 analysis queries demonstrate joins, CTEs, CASE logic, filtered aggregates, percentiles, `ROW_NUMBER`, `RANK`, `PERCENT_RANK`, `NTILE`, `LAG`, rolling windows, and IQR anomaly detection.

## How did you ensure data quality?

I defined completeness, validity, uniqueness, and referential-integrity rates, plus cross-fact rules. Python validates data before load and PostgreSQL repeats the critical controls with constraints. Every rejected row is auditable in a quarantine dataset; every correction has an action and final result; pytest covers boundaries and business rules. The processed composite is 100% for the defined critical checks, while soft pricing anomalies remain visible rather than being deleted.

## What was the most difficult data issue?

The hardest issue was an accepted quote becoming un-loadable because its date, amount, or dealer key failed a hard rule. Keeping the inquiry as converted would break the one-winner rule and overstate performance. The pipeline therefore downgrades that inquiry to non-converted, clears sale/winner fields, and records the correction. In the full run, 104 outcomes were handled this way.

## How did you define KPIs?

I started from the decision and grain. Conversion rate is converted inquiries divided by inquiries. Dealer win rate is accepted dealer quotes divided by that dealer's quote count. Quote spread is calculated once per inquiry. Quote-to-market ratio is amount divided by appraisal at quote grain. I document the denominator next to every KPI to prevent misleading comparisons.

## What DAX measures did you create?

The library includes inquiry/quote volume, conversion, average/median/max/min quote, high/low/spread, accepted value, response, SLA, dealer wins/rank, competitiveness, active dealers, MoM/YoY growth, rolling conversion, previous-period conversion, quote anomalies, and all data-quality/pipeline metrics. Non-trivial measures use variables, `USERELATIONSHIP`, `CROSSFILTER`, `DATEADD`, `SAMEPERIODLASTYEAR`, and `RANKX`.

## What is the difference between a calculated column and a measure?

A calculated column is evaluated row by row at data refresh and stored in the model; it is useful for stable categories such as age or mileage bands. A measure is evaluated at query time in filter context and should be used for totals, rates, rankings, and time intelligence. I calculate stable data-engineering fields in Python/SQL and use DAX measures for interactive aggregation.

## Why avoid bidirectional relationships?

Bidirectional filters can create ambiguous paths and make totals depend on unexpected propagation. This model uses single-direction filters from dimensions to facts and from inquiry header to quote line. Quote-date analysis activates the inactive date relationship explicitly and disables the default inquiry/quote path within that measure.

## How did you optimize SQL?

I aligned indexes to high-frequency date filters and fact joins: inquiry date/customer/vehicle/winner, quote inquiry/dealer/date, and partial indexes for accepted quotes and anomalies. Views keep BI queries at the correct grain. Analytical queries aggregate before ranking, use volume thresholds, and avoid counting inquiries through raw quote joins.

## How would the system scale?

I would ingest incrementally into object storage, partition facts by date, use warehouse-native bulk load or merge, maintain surrogate keys/SCD handling where needed, and orchestrate with Airflow or Dagster. Quality metrics would be partition-aware, recent periods would allow late arrivals, and Power BI would use incremental refresh or aggregations.

## What would you change in production?

I would replace synthetic CSV generation with governed source contracts; add run IDs, source timestamps, lineage, alerting, and retry/idempotency; keep secrets in a vault; classify personal data; add role-based access; validate appraisals against an independent pricing source; include acquisition cost and dealer fee/margin; and deploy Power BI through development/test/production workspaces.

## What insights did you discover?

Inquiries grew 32.1% from 2022 to 2025 while conversion stayed near 32%. A first quote inside eight hours was associated with 33.27% conversion versus 29.43% later. Dealer Referral converted at 38.43%, 11.62 points above Social Media. Accepted quotes were closer to market and faster. SUVs produced 51.45% of accepted value, and 10+ year vehicles had 2.03 times the relative quote spread of 0–2 year vehicles.

## How did the analysis create business value?

It converted raw activity into actions: an eight-hour response SLA, a volume-guarded dealer scorecard, referral-channel protection, SUV coverage planning, relative-spread monitoring for older vehicles, and a pricing-review queue for 1,162 soft anomalies. The data-quality page also shows why commercial metrics can be trusted.

## How would you communicate this to a non-technical stakeholder?

I would start with the decision: demand is growing, but conversion is not. Then I would show three actionable comparisons—fast versus slow first response, referral versus social leads, and competitive versus non-accepted quotes—using plain percentages and volumes. I would finish with owners and next steps, and keep methodology available as supporting evidence rather than leading with code.

## Two-minute project story

> I modeled a marketplace where 100,000 customer inquiries receive about 345,000 dealer quotes. The core challenge was not producing charts; it was keeping inquiry conversion and dealer quote performance at the right grains while handling deliberately messy raw data. Python creates and cleans the data, PostgreSQL enforces the model and supports advanced analysis, and Power BI is specified as a five-page operating report. The full run kept 99,813 inquiries and 343,120 quotes, passed all critical curated checks, and surfaced concrete actions around an eight-hour response SLA, referral-channel quality, dealer competitiveness, older-vehicle spread, and pricing anomalies. The project demonstrates the complete path from data reliability to stakeholder decision.
