# Project Audit — Swiss Junior Analytics Hiring Review

## 60-second decision

**Interview for a Junior Data Analyst role: yes.** The repository is a credible synthetic case study rather than a production project, but it demonstrates enough implementation depth, analytical judgement, and honesty to justify a technical interview.

**Do not treat it as proof of Power BI Service ownership yet.** The checked-in PBIP is real, editable, PostgreSQL-backed, and data-bound. It opens in Power BI Desktop, refreshes from PostgreSQL, and renders all five pages, including the repaired KPI cards and dealer rankings. PostgreSQL 16.14, the full load, SQL analytics, database quality checks, views, indexes, and constraints have also been validated live.

## Critical scorecard

| Hiring question | Verdict | Evidence and concern |
|---|---|---|
| 1. Real analytics project or tutorial? | **Credible case study; not production** | The grains, reconciliation, quality treatments, business decisions, tests, and generated deliverables go beyond a tutorial. The data and relationships are deliberately generated, so the candidate has not demonstrated source-system ambiguity, stakeholder conflict, or production operations. |
| 2. Is the SQL sufficiently advanced? | **Yes for junior level** | 24 PostgreSQL analyses use CTEs, filtered aggregates, percentiles, window ranking, `LAG`, rolling frames, `NTILE`, `PERCENT_RANK`, and IQR logic. All 69 SQL statements parse and all 24 analyses execute successfully against PostgreSQL 16.14. Query-plan and concurrency evidence remain outside this portfolio validation. |
| 3. Is the data model professional? | **Yes, with correct terminology** | It is a fact constellation: inquiry header plus quote line, conformed dimensions, explicit grains, single-direction BI relationships, inactive quote-date role, database constraints, and a partial unique index enforcing one accepted quote per inquiry. It is not misrepresented as a pure star. |
| 4. Are the KPIs meaningful? | **Mostly** | Conversion, dealer win rate, accepted value, response SLA, quote spread, competitiveness, anomalies, and quality metrics have documented denominators and decision use. CAC, dealer fees, contribution margin, and targets are absent because the synthetic source does not contain them. |
| 5. Is Power BI genuinely demonstrated? | **Yes** | `AutomotiveCommercialAnalytics.pbip` opens in Power BI Desktop, loads PostgreSQL data, and contains 5 manually reviewed PBIR pages, 59 bound visuals, 9 imported tables, 6 business relationships, and 55 measures attached to real imported tables. Five genuine Desktop captures are included. |
| 6. Are the DAX measures useful and correct? | **Strong for junior level** | Measures separate inquiry conversion from quote win rate, use ratio-of-sums where aggregation demands it, apply volume guards to dealer rank, and handle the inactive quote-date role with `USERELATIONSHIP` plus `CROSSFILTER`. The populated report visuals and cards were manually reviewed after refresh. |
| 7. Is data quality handled seriously? | **Yes for a static case study** | Raw and Processed use the same completeness, validity, uniqueness, and integrity checks. The composite reconciles exactly to passed/applicable checks. Twenty-two pre-load assertions pass, all 10 live database-quality queries pass, and the first nine return zero rule failures. Correction, quarantine, and soft flags are distinct. Production freshness/drift alerting is only documented. |
| 8. Are insights supported by data? | **Yes, with a synthetic-data ceiling** | Exact evidence is persisted in JSON/CSV, the notebook executes without errors, denominators are stated, and the response/channel findings remain directionally consistent within every year. Wilson intervals are persisted for response groups. Because the generator embeds relationships, these are demonstrations of method, not market discovery or causal estimates. |
| 9. Does the README communicate value in 30 seconds? | **Yes** | The opening section now states scope and limits, then links business outcomes to SQL, model, PBIP, Excel, trust controls, and unresolved handoffs before the architecture detail. |
| 10. Anything generic, fake, repetitive, or unnecessary? | **Reduced; some signals remain** | The previous self-audit was implausibly positive and has been replaced. The screenshots are genuine Power BI Desktop captures, no `.pbix` is fabricated, and claims distinguish Desktop validation from Power BI Service deployment. The unusually broad documentation and neat synthetic patterns may still look AI-assisted; the interview should test whether the candidate can explain and modify the implementation. |
| 11. Obvious junior analyst skills missing? | **No critical baseline gap** | SQL, Python, Excel, Power BI source, DAX, data modelling, DQ, charts, notebook analysis, GitHub Actions, and stakeholder writing are visible. Missing production exposure includes a real source, incremental orchestration, cloud deployment, access control, and live Power BI service operations. |
| 12. Does it strengthen target applications? | **Yes, unevenly** | Strongest for Data Analyst and analytics-oriented Junior Data Engineer applications. Useful for Business/Analytics roles. BI Analyst value is conditional on the candidate opening, refreshing, and presenting the PBIP in Desktop. |

## Material weaknesses found and fixed

| Severity | Weakness found | Repository change |
|---|---|---|
| High | Overall quality rate did not equal its own numerator/denominator. | Replaced the mixed unweighted/weighted calculation with a check-weighted composite that reconciles exactly. |
| High | Raw and Processed quality scores used different rule scopes. | Centralized like-for-like required-field, domain, PK, and FK checks for both stages. |
| High | Power BI was initially represented only by prose and a static dashboard image. | Added a source-controlled PBIP, 59 bound visuals across five pages, and five genuine Power BI Desktop screenshots. |
| High | No Excel evidence for a junior analyst portfolio. | Added a generated 7-sheet decision workbook with 577 formulas, 3 charts, conditional formatting, tables, rankings, reconciliation, and field profiling. |
| High | `to_sql(method="multi", chunksize=10000)` could exceed PostgreSQL's bind-parameter limit on wide facts. | Added a column-aware 50,000-parameter budget and JSONB preparation for quarantine payloads. |
| High | The database did not enforce the one-accepted-quote rule. | Added a partial unique index on `fact_quote(inquiry_id) WHERE accepted_flag`. |
| High | Power BI Desktop rejected the synthetic calculated `Measures` table used only as a measure container. | Removed the table, partition, and placeholder column; retained the original 47 measures on real imported tables. Eight report-specific measures bring the current total to 55 across six real tables. |
| High | Power BI Desktop found `pServer` and `pDatabase` in both `model.tmdl` and `expressions.tmdl`. | Removed the duplicate model-fragment declarations, kept each parameter once in `expressions.tmdl`, and added regression checks for unique named expressions and partition references. |
| Medium | Processed checks omitted date coverage, status/outcome, accepted value, and persisted fact summaries. | Expanded the pre-load contract from 13 to 22 critical assertions. |
| Medium | Quality-stage improvement relied on lexical `ORDER BY stage DESC`. | Replaced it with explicit Raw → Processed ordering. |
| Medium | The quote-date DAX measure disabled the inquiry-to-quote relationship and therefore dropped vehicle/customer/channel filters. | It now disables only Date → Inquiry while activating Date → Quote, preserving other inquiry attributes. |
| Medium | Headline channel/response insights could be portfolio-mix artefacts. | Added by-year stability tables and 95% Wilson intervals; updated notebook and findings. |
| Medium | README and CV language overclaimed a pure star and Power BI readiness. | Renamed the model as a fact constellation and separated schema validation from Desktop proof. |
| Medium | The previous audit scored every area above 9 and looked self-generated. | Replaced it with role-specific hiring decisions, concrete risks, and unresolved handoffs. |
| Medium | Direct `pytest` execution could not import `src`. | Added `pytest.ini`; both `pytest -q` and CI-style invocation now work. |
| Medium | The documented `.env` file was never loaded and connection defaults were evaluated at import time. | `.env` is now loaded and `DatabaseConfig` resolves environment values at instantiation. |
| Medium | Excel CHF formats reopened as date/error cells. | Quoted the currency literal and made workbook validation reject error cells. |
| Medium | Power BI Desktop rejected `en-CH` model and source-query cultures because both resolved to LCID 4096 in the SQLSort runtime. | Aligned `Model.Culture` and `Model.SourceQueryCulture` to `en-US`, matching database language `1033`; the next Desktop open cleared the LCID failure. |
| Low | Full-scale CSVs make the Git repository unusually large. | Added `data/README.md` explaining the 84 MB fixture trade-off and production alternatives. |

## Role fit after remediation

| Target role | Hiring-manager view | Interview strength |
|---|---|---:|
| Data Analyst | **Interview** | 8.5/10 |
| BI Analyst | **Conditional interview** — require a live Desktop walkthrough | 7.5/10 |
| Junior Data Engineer | **Interview** — probe incremental design, orchestration, and operational ownership | 8.0/10 |
| Business Analyst / Analytics | **Interview** — probe requirements gathering, finance, and stakeholder trade-offs | 8.2/10 |

These scores are portfolio-fit judgements, not claims of production seniority.

## Final validation evidence

| Check | Result |
|---|---|
| Full pipeline with database | Passed full-scale generation, extraction, transformation, 22 pre-load assertions, analysis evidence, Excel, PBIP generation, notebook execution, and transactional PostgreSQL load |
| Curated scale | 50,000 customers; 99,923 vehicles; 150 dealers; 99,813 inquiries; 343,120 quotes |
| Database/source reconciliation | 10/10 PostgreSQL table counts exactly match their curated CSV row counts |
| Data-quality reconciliation | Raw: 7,743,556 / 7,747,628 = 99.947%; Processed: 7,710,401 / 7,710,401 = 100% |
| Live SQL analytics | 24/24 passed; every query returned rows, including all CTE, join, aggregate, percentile, and window-function analyses |
| Live database quality SQL | 10/10 passed; queries 1–9 returned zero failures and query 10 returned the 18-row operational issue summary |
| Views | 5/5 queryable; inquiry and quote views reconcile to 99,813 and 343,120 fact rows |
| Indexes | 13/13 declared secondary indexes exist and are valid/ready, including the partial unique accepted-quote index |
| Constraints | 37/37 validated; rolled-back checks confirmed CHECK, foreign-key, and one-accepted-quote enforcement |
| Headline fact reconciliation | 32,464 converted inquiries = 32,464 accepted quotes; both facts total CHF 695,085,974.67 accepted value |
| `pytest -q` | 29 passed |
| Ruff | All checks passed |
| PostgreSQL syntax | 6 files, 69 statements parsed; 24 numbered analytical queries |
| Load validation | 22/22 assertions passed; all 10 tables loaded and PostgreSQL-safe chunk sizes tested |
| PBIR | 5 pages, 59 visuals; Microsoft validator offline structural pass: 0 errors, 0 warnings. The online run returned 0 errors and one schema-reachability warning for Desktop's visual-container schema version 2.11.0. |
| TMDL | Microsoft `TmdlSerializer`: 12 tables and 8 relationships parsed after the final Desktop save—9 imported business tables and 6 business relationships, plus 3 hidden Desktop auto-date tables and 2 hidden date relationships. All 55 measures have valid real home tables. |
| Power BI Desktop open | Passed manual validation: the project opens, refreshes all nine PostgreSQL tables, and renders all five pages, 21 KPI cards, and corrected Top-N dealer charts. |
| Excel | 7 sheets, 577 formulas, 3 charts, zero error cells after reopen |
| Notebook | 34 cells; 18/18 code cells executed; zero error outputs |
| Docker Compose | PostgreSQL 16.14 container running healthy on port 5432; persistent named volume active |

## Remaining interview risks and required handoff

1. **Power BI operations:** Desktop validation is complete, but Power BI Service deployment, scheduled refresh, gateway configuration, workspace permissions, and row-level security remain outside this portfolio release.
2. **Synthetic-data bias:** Ask the candidate to explain which findings were encoded by the generator and how they would validate them on messy real data.
3. **Production design:** The successful local full refresh does not prove incremental loads, concurrency, query-plan tuning, SCD strategy, orchestration, late arrivals, source contracts, observability, secrets management, PII controls, RLS, or deployment environments.
4. **Business completeness:** Channel recommendations need acquisition cost; dealer decisions need fees/margin and agreed targets. The repository correctly labels those fields as unavailable rather than inventing them.

## Bottom line

This repository would move a junior candidate from “unknown” to “worth interviewing.” It now includes live PostgreSQL execution evidence in addition to the file artifacts. It does not, by itself, prove professional Power BI delivery, production data engineering, or real stakeholder experience; those are the correct focus areas for the interview.
