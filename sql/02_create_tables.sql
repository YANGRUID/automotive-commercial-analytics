SET search_path TO automotive_analytics, public;

CREATE TABLE IF NOT EXISTS dim_date (
    date DATE PRIMARY KEY,
    year SMALLINT NOT NULL,
    quarter VARCHAR(2) NOT NULL,
    month SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name VARCHAR(12) NOT NULL,
    week SMALLINT NOT NULL CHECK (week BETWEEN 1 AND 53),
    day_of_week VARCHAR(10) NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id VARCHAR(8) PRIMARY KEY,
    customer_created_date DATE NOT NULL,
    age_group VARCHAR(10) NOT NULL,
    canton VARCHAR(10) NOT NULL,
    customer_type VARCHAR(20) NOT NULL,
    preferred_contact_method VARCHAR(20) NOT NULL,
    lead_source VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_vehicle (
    vehicle_id VARCHAR(9) PRIMARY KEY,
    brand VARCHAR(30) NOT NULL,
    model VARCHAR(50) NOT NULL,
    vehicle_type VARCHAR(20) NOT NULL,
    fuel_type VARCHAR(20) NOT NULL,
    manufacture_year SMALLINT NOT NULL CHECK (manufacture_year BETWEEN 1990 AND 2025),
    mileage_km INTEGER NOT NULL CHECK (mileage_km BETWEEN 0 AND 500000),
    estimated_market_value NUMERIC(12, 2) NOT NULL CHECK (estimated_market_value > 0),
    vehicle_condition VARCHAR(15) NOT NULL,
    mileage_bracket VARCHAR(20) NOT NULL,
    market_value_band VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_dealer (
    dealer_id VARCHAR(5) PRIMARY KEY,
    dealer_name VARCHAR(100) NOT NULL,
    dealer_region VARCHAR(40) NOT NULL,
    dealer_type VARCHAR(30) NOT NULL,
    dealer_rating NUMERIC(3, 2) NOT NULL CHECK (dealer_rating BETWEEN 0 AND 5),
    active_flag BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_inquiry (
    inquiry_id VARCHAR(9) PRIMARY KEY,
    customer_id VARCHAR(8) NOT NULL REFERENCES dim_customer(customer_id),
    vehicle_id VARCHAR(9) NOT NULL REFERENCES dim_vehicle(vehicle_id),
    inquiry_date DATE NOT NULL REFERENCES dim_date(date),
    lead_source VARCHAR(30) NOT NULL,
    status VARCHAR(15) NOT NULL CHECK (status IN ('Converted', 'Lost', 'Expired', 'Open')),
    final_sale_price NUMERIC(12, 2),
    winning_dealer_id VARCHAR(5) REFERENCES dim_dealer(dealer_id),
    conversion_flag BOOLEAN NOT NULL,
    days_to_conversion SMALLINT,
    quote_count SMALLINT NOT NULL CHECK (quote_count > 0),
    highest_quote NUMERIC(12, 2) NOT NULL,
    lowest_quote NUMERIC(12, 2) NOT NULL,
    average_quote NUMERIC(12, 2) NOT NULL,
    fastest_response_hours NUMERIC(8, 2) NOT NULL,
    quote_spread NUMERIC(12, 2) NOT NULL CHECK (quote_spread >= 0),
    quote_spread_pct NUMERIC(10, 4) NOT NULL CHECK (quote_spread_pct >= 0),
    vehicle_age_at_inquiry SMALLINT NOT NULL CHECK (vehicle_age_at_inquiry >= 0),
    CONSTRAINT inquiry_conversion_consistency CHECK (
        (conversion_flag AND final_sale_price IS NOT NULL AND winning_dealer_id IS NOT NULL)
        OR
        (NOT conversion_flag AND final_sale_price IS NULL AND winning_dealer_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS fact_quote (
    quote_id VARCHAR(10) PRIMARY KEY,
    inquiry_id VARCHAR(9) NOT NULL REFERENCES fact_inquiry(inquiry_id),
    dealer_id VARCHAR(5) NOT NULL REFERENCES dim_dealer(dealer_id),
    quote_date DATE NOT NULL REFERENCES dim_date(date),
    quote_amount NUMERIC(12, 2) NOT NULL CHECK (quote_amount > 0 AND quote_amount <= 500000),
    response_time_hours NUMERIC(8, 2) NOT NULL CHECK (response_time_hours >= 0),
    quote_rank SMALLINT NOT NULL CHECK (quote_rank > 0),
    accepted_flag BOOLEAN NOT NULL,
    estimated_market_value NUMERIC(12, 2) NOT NULL CHECK (estimated_market_value > 0),
    quote_to_market_ratio NUMERIC(8, 4) NOT NULL CHECK (quote_to_market_ratio > 0),
    anomaly_flag BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS data_quality_metrics (
    metric_name VARCHAR(50) NOT NULL,
    stage VARCHAR(15) NOT NULL CHECK (stage IN ('Raw', 'Processed')),
    passed_records BIGINT NOT NULL,
    total_records BIGINT NOT NULL,
    rate NUMERIC(10, 6) NOT NULL CHECK (rate BETWEEN 0 AND 1),
    description TEXT NOT NULL,
    assessment_date DATE NOT NULL,
    PRIMARY KEY (metric_name, stage, assessment_date)
);

CREATE TABLE IF NOT EXISTS data_quality_issue_log (
    issue_id VARCHAR(8) PRIMARY KEY,
    table_name VARCHAR(40) NOT NULL,
    issue_type VARCHAR(80) NOT NULL,
    affected_rows BIGINT NOT NULL CHECK (affected_rows >= 0),
    action TEXT NOT NULL,
    final_result TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantined_records (
    quarantine_id VARCHAR(12) PRIMARY KEY,
    table_name VARCHAR(40) NOT NULL,
    record_id VARCHAR(50) NOT NULL,
    issue_type VARCHAR(80) NOT NULL,
    action TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    record_payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_run_summary (
    table_name VARCHAR(40) PRIMARY KEY,
    raw_records BIGINT NOT NULL,
    duplicate_records BIGINT NOT NULL,
    corrected_records BIGINT NOT NULL,
    quarantined_records BIGINT NOT NULL,
    clean_records BIGINT NOT NULL,
    loaded_records BIGINT NOT NULL,
    load_status VARCHAR(20) NOT NULL
);
