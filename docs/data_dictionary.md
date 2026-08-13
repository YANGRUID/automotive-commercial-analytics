# Data Dictionary

All currency values are Swiss francs (CHF). IDs are stable synthetic business keys.

## `dim_customer` — one row per customer

| Column | Type | Meaning |
|---|---|---|
| `customer_id` | text, PK | Synthetic customer identifier |
| `customer_created_date` | date | Registration date before first inquiry |
| `age_group` | text | Customer age band |
| `canton` | text | Swiss canton code or explicit `Unknown` |
| `customer_type` | text | Private, Business, or Fleet |
| `preferred_contact_method` | text | Email, Phone, SMS, or WhatsApp |
| `lead_source` | text | Customer's primary acquisition source |

## `dim_vehicle` — one row per appraised vehicle

| Column | Type | Meaning |
|---|---|---|
| `vehicle_id` | text, PK | Synthetic vehicle identifier |
| `brand`, `model` | text | Canonical vehicle make/model |
| `vehicle_type` | text | SUV, Hatchback, Sedan, Estate, Van, or Sports |
| `fuel_type` | text | Petrol, Diesel, Hybrid, Electric, or Unknown |
| `manufacture_year` | integer | Model manufacture year |
| `mileage_km` | integer | Validated odometer reading, 0–500,000 km |
| `estimated_market_value` | decimal | Synthetic appraisal in CHF |
| `vehicle_condition` | text | Excellent, Good, Fair, or Poor |
| `mileage_bracket` | text | Ordered reporting band derived in ETL |
| `market_value_band` | text | Ordered value band derived in ETL |

## `dim_dealer` — one row per dealer

| Column | Type | Meaning |
|---|---|---|
| `dealer_id` | text, PK | Synthetic dealer identifier |
| `dealer_name` | text | Fictional dealer name |
| `dealer_region` | text | One of seven Swiss commercial regions |
| `dealer_type` | text | Franchise, Independent, or Online Specialist |
| `dealer_rating` | decimal | Synthetic 0–5 rating |
| `active_flag` | boolean | Whether dealer is active at snapshot date |

## `fact_inquiry` — one row per inquiry

| Column | Type | Meaning |
|---|---|---|
| `inquiry_id` | text, PK | Inquiry identifier |
| `customer_id`, `vehicle_id` | text, FK | Customer and vehicle parents |
| `inquiry_date` | date, FK | Date the inquiry entered the marketplace |
| `lead_source` | text | Source attributed to this inquiry |
| `status` | text | Converted, Lost, Expired, or Open |
| `final_sale_price` | decimal, nullable | Accepted quote amount for converted inquiries |
| `winning_dealer_id` | text, nullable | Dealer on the accepted quote |
| `conversion_flag` | boolean | Inquiry converted |
| `days_to_conversion` | integer, nullable | Days from inquiry to conversion |
| `quote_count` | integer | Curated quotes received |
| `highest_quote`, `lowest_quote`, `average_quote` | decimal | Inquiry-level valid quote statistics |
| `fastest_response_hours` | decimal | Earliest valid dealer response |
| `quote_spread` | decimal | Highest minus lowest valid quote in CHF |
| `quote_spread_pct` | decimal | Quote spread divided by lowest quote |
| `vehicle_age_at_inquiry` | integer | Inquiry year minus manufacture year |

## `fact_quote` — one row per dealer quote

| Column | Type | Meaning |
|---|---|---|
| `quote_id` | text, PK | Quote identifier |
| `inquiry_id`, `dealer_id` | text, FK | Inquiry and dealer parents |
| `quote_date` | date, FK | Calendar date of response |
| `quote_amount` | decimal | Positive, hard-valid quote in CHF |
| `response_time_hours` | decimal | Dealer response elapsed time |
| `quote_rank` | integer | Descending amount rank within inquiry |
| `accepted_flag` | boolean | One accepted quote for each converted inquiry |
| `estimated_market_value` | decimal | Appraisal copied to quote grain for efficient ratios |
| `quote_to_market_ratio` | decimal | Quote divided by appraisal |
| `anomaly_flag` | boolean | Soft business exception outside 0.70–1.08 ratio |

## `dim_date` — one row per calendar date

Date, year, quarter, month number/name, ISO week, day name, and weekend flag for 2022–2025.

## Quality and operations tables

| Table | Grain | Purpose |
|---|---|---|
| `data_quality_metrics` | quality metric × pipeline stage × assessment date | Raw vs processed completeness, validity, uniqueness, integrity, and composite score |
| `data_quality_issue_log` | issue/action summary | Affected rows, corrective action, and final result |
| `quarantined_records` | detected rejected issue | Record ID, table, issue, action, timestamp, and original row payload |
| `pipeline_run_summary` | pipeline table | Raw, duplicate, corrected, quarantined, clean, loaded counts and load state |
