# Business Requirements

## Business problem

A fictional Swiss automotive quotation marketplace receives vehicle sale inquiries and distributes them to competing dealers. Management needs a single analytical product that explains demand, pricing dispersion, dealer competitiveness, customer conversion, channel quality, response speed, commercial value, and data reliability.

## Stakeholders and decisions

| Stakeholder | Decision supported |
|---|---|
| General management | Whether marketplace volume, conversion, and accepted value are improving |
| Commercial lead | Which channels, brands, models, and vehicle segments deserve investment |
| Dealer operations | Which dealers need SLA, competitiveness, or performance intervention |
| Pricing analyst | Where quote spreads or quote-to-market ratios are unusual |
| Data/BI team | Whether the pipeline is complete, valid, unique, and referentially consistent |

## Required business questions

1. How many customer inquiries and dealer quotes are received?
2. Which dealers make the most competitive offers?
3. How wide is the highest-to-lowest quote spread?
4. Which vehicle brands, models, and segments generate the most value?
5. Which dealers have the strongest quote win rates?
6. How quickly do dealers respond?
7. Which customer and vehicle attributes are associated with conversion?
8. Which lead sources generate high-volume, high-conversion inquiries?
9. Which quotations or records require quality review?
10. How do volume, conversion, and value change over time?

## KPI definitions

| KPI | Definition | Grain / denominator |
|---|---|---|
| Total Inquiries | Distinct curated inquiry IDs | Inquiry |
| Total Quotes | Distinct curated quote IDs | Quote |
| Converted Inquiries | Distinct inquiries with `conversion_flag = TRUE` | Inquiry |
| Conversion Rate | Converted inquiries / total inquiries | Inquiry |
| Dealer Win Rate | Accepted quotes / all quotes for that dealer | Dealer-quote |
| Average Sale Value | Mean final sale price among converted inquiries | Converted inquiry |
| Quote Spread | Highest minus lowest valid quote for one inquiry | Inquiry |
| Quote-to-Market Ratio | Quote amount / estimated market value | Quote |
| Average Response Time | Mean dealer response time in hours | Quote |
| SLA Compliance | Inquiries with fastest response under eight hours / inquiries | Inquiry |
| Data Quality Score | Mean of completeness, validity, uniqueness, and referential-integrity rates | Pipeline assessment |

## Scope

- Synthetic, non-proprietary data representing January 2022 through December 2025.
- Swiss cantons and seven commercial dealer regions.
- PostgreSQL analytical store with Python/Pandas ETL.
- Power BI model and report specification; no fabricated `.pbix` binary.
- Management insights are descriptive and derived from the generated data.

## Out of scope

- Real personal data, live dealer integrations, vehicle VINs, payments, finance margin, and production deployment.
- Causal attribution of conversion differences.
- Forecasting, machine learning, geospatial routing, and dealer contract enforcement.

## Acceptance criteria

- The generator is deterministic with seed 42 and produces approximately 50k customers, 100k inquiries, 250k–400k quotes, and 100–200 dealers.
- Curated primary keys are unique; foreign keys resolve; quote/date/conversion rules pass.
- Hard-invalid records are quarantined and auditable; defensible corrections are logged.
- PostgreSQL DDL is idempotent and includes constraints, indexes, views, and at least 20 meaningful analytical queries.
- The notebook executes top-to-bottom without error.
- Every reported insight is traceable to `data/processed/analysis_summary.json` or a curated table.
- Tests run in CI and locally with `pytest`.
- Power BI measures distinguish inquiry conversion from quote win rate.
