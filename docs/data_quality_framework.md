# Data Quality Framework

## Operating principle

Quality controls distinguish between **correction**, **quarantine**, and **flagging**. A record is corrected only when intent is defensible (for example, trimming whitespace or reversing a negative mileage sign whose magnitude is valid). A record is quarantined when repair would invent business data. A positive, referentially valid but unusual quote remains available with `anomaly_flag = TRUE`.

## Quality dimensions

| Dimension | Formula | Core controls |
|---|---|---|
| Completeness | populated required fields / required field cells | Required IDs, dates, categories, values; optional conversion fields excluded when not applicable |
| Validity | domain-valid checks / applicable checks | Mileage, quote amount, market value, rating, parseable dates, response time |
| Uniqueness | non-duplicate primary-key rows / primary-key rows | Customer, vehicle, dealer, inquiry, quote, date keys |
| Referential integrity | resolving foreign keys / foreign-key checks | Inquiry-to-customer/vehicle and quote-to-inquiry/dealer; optional winner keys |
| Overall score | passed checks across four dimensions / applicable checks across four dimensions | Check-weighted composite reported separately for Raw and Processed stages |

Raw and Processed use the same required-field, domain, primary-key, and foreign-key rule set, so the stage comparison is like-for-like. The processed score reaches 100% because every retained row passes those defined checks. It is not a claim that the synthetic data is perfect in every possible business sense; 1,162 soft quote anomalies remain intentionally visible.

## Critical business rules

- Primary IDs are non-null and unique.
- `0 <= mileage_km <= 500000`.
- `1990 <= manufacture_year <= 2025` and `0 <= dealer_rating <= 5`.
- `0 < quote_amount <= 500000`.
- Quote response time is non-negative.
- Quote dealer and inquiry keys resolve.
- Inquiry customer and vehicle keys resolve.
- Inquiry and quote dates resolve to the explicit date dimension.
- Quote date is on or after inquiry date.
- A converted inquiry has exactly one accepted quote; a non-converted inquiry has none.
- Converted status, winning dealer, and final sale price equal the accepted outcome.
- Persisted quote count, high, low, average, and fastest response reconcile to quote rows.

## Actual run evidence

| Issue | Affected rows | Treatment |
|---|---:|---|
| Invalid quote foreign key | 973 | Quarantined |
| Invalid quote date/amount domain | 779 | Quarantined |
| Missing response time | 687 | Dealer median, portfolio-median fallback |
| Duplicate quote key | 517 | First deterministic row retained; duplicate quarantined |
| Missing fuel type | 333 | Explicit Unknown member |
| Missing canton | 200 | Explicit Unknown member |
| Inconsistent lead-source text | 166 | Trimmed and canonicalized |
| Duplicate inquiry key | 150 | Duplicate quarantined |
| Malformed inquiry date | 111 | Quarantined |
| Conversion whose accepted quote was rejected | 104 | Downgraded to non-converted to prevent overstatement |
| Invalid vehicle domain | 77 | Quarantined |
| Negative mileage sign | 76 | Absolute value only when magnitude is valid |
| Winning dealer mismatch | 48 | Re-derived from accepted quote |

The quarantine dataset contains 2,735 issue occurrences across 2,731 unique record IDs. The difference occurs when the duplicate and retained instance of the same business key fail separate rules.

## Monitoring and ownership

| Rule | Severity | Automation | Owner/action |
|---|---|---|---|
| Duplicate fact/dimension key | Critical | Every run | Data engineering blocks load |
| Broken foreign key | Critical | Every run | Quarantine and investigate source mapping |
| Accepted/winner inconsistency | Critical | Every run | Reconcile or downgrade outcome |
| Invalid quote/mileage domain | High | Every run | Quarantine; source remediation |
| Missing optional category | Medium | Every run | Map to Unknown and monitor trend |
| Soft quote-to-market anomaly | Medium | Every run | Retain and send to pricing review |
| Whitespace/casing | Low | Every run | Normalize automatically |

## Evidence locations

- Python rules: `src/data_quality.py` and `src/transform.py`
- SQL controls: `sql/06_data_quality_queries.sql`
- Automated tests: `tests/test_data_quality.py` and `tests/test_business_rules.py`
- Persisted evidence: `data/processed/data_quality_*.csv`, `quarantined_records.csv`, and `pipeline_run_summary.csv`
