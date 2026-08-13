SET search_path TO automotive_analytics, public;

-- Date and entity indexes support the dashboard's most common filters and joins.
CREATE INDEX IF NOT EXISTS idx_fact_inquiry_date
    ON fact_inquiry (inquiry_date);
CREATE INDEX IF NOT EXISTS idx_fact_inquiry_customer
    ON fact_inquiry (customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_inquiry_vehicle
    ON fact_inquiry (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_fact_inquiry_winner
    ON fact_inquiry (winning_dealer_id)
    WHERE winning_dealer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fact_inquiry_conversion_date
    ON fact_inquiry (conversion_flag, inquiry_date);

CREATE INDEX IF NOT EXISTS idx_fact_quote_inquiry
    ON fact_quote (inquiry_id);
CREATE INDEX IF NOT EXISTS idx_fact_quote_dealer
    ON fact_quote (dealer_id);
CREATE INDEX IF NOT EXISTS idx_fact_quote_date
    ON fact_quote (quote_date);
CREATE INDEX IF NOT EXISTS idx_fact_quote_accepted_dealer
    ON fact_quote (dealer_id, accepted_flag)
    WHERE accepted_flag;
-- Enforce the commercial invariant at the database layer, not only in Python.
CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_quote_one_accepted_per_inquiry
    ON fact_quote (inquiry_id)
    WHERE accepted_flag;
CREATE INDEX IF NOT EXISTS idx_fact_quote_anomaly
    ON fact_quote (anomaly_flag)
    WHERE anomaly_flag;

CREATE INDEX IF NOT EXISTS idx_dim_vehicle_brand_type
    ON dim_vehicle (brand, vehicle_type);
CREATE INDEX IF NOT EXISTS idx_dim_customer_canton_source
    ON dim_customer (canton, lead_source);
