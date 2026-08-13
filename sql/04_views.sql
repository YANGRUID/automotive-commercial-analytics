SET search_path TO automotive_analytics, public;

CREATE OR REPLACE VIEW vw_inquiry_analytics AS
SELECT
    i.inquiry_id,
    i.inquiry_date,
    DATE_TRUNC('month', i.inquiry_date)::date AS inquiry_month,
    i.status,
    i.conversion_flag,
    i.final_sale_price,
    i.days_to_conversion,
    i.quote_count,
    i.highest_quote,
    i.lowest_quote,
    i.average_quote,
    i.quote_spread,
    i.quote_spread_pct,
    i.fastest_response_hours,
    i.vehicle_age_at_inquiry,
    i.lead_source,
    c.customer_type,
    c.age_group,
    c.canton,
    c.preferred_contact_method,
    v.brand,
    v.model,
    v.vehicle_type,
    v.fuel_type,
    v.mileage_km,
    v.mileage_bracket,
    v.estimated_market_value,
    v.vehicle_condition,
    i.winning_dealer_id
FROM fact_inquiry AS i
JOIN dim_customer AS c ON c.customer_id = i.customer_id
JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id;

CREATE OR REPLACE VIEW vw_quote_competitiveness AS
SELECT
    q.quote_id,
    q.inquiry_id,
    q.dealer_id,
    d.dealer_name,
    d.dealer_region,
    q.quote_date,
    q.quote_amount,
    q.response_time_hours,
    q.quote_rank,
    q.accepted_flag,
    q.estimated_market_value,
    q.quote_to_market_ratio,
    q.anomaly_flag,
    v.brand,
    v.model,
    v.vehicle_type
FROM fact_quote AS q
JOIN dim_dealer AS d ON d.dealer_id = q.dealer_id
JOIN fact_inquiry AS i ON i.inquiry_id = q.inquiry_id
JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id;

CREATE OR REPLACE VIEW vw_dealer_performance AS
SELECT
    d.dealer_id,
    d.dealer_name,
    d.dealer_region,
    d.dealer_type,
    d.dealer_rating,
    d.active_flag,
    COUNT(q.quote_id) AS total_quotes,
    COUNT(q.quote_id) FILTER (WHERE q.accepted_flag) AS accepted_quotes,
    ROUND(
        COUNT(q.quote_id) FILTER (WHERE q.accepted_flag)::numeric
        / NULLIF(COUNT(q.quote_id), 0),
        4
    ) AS dealer_win_rate,
    ROUND(AVG(q.response_time_hours), 2) AS average_response_time_hours,
    ROUND(AVG(q.quote_to_market_ratio), 4) AS average_quote_to_market_ratio,
    ROUND(SUM(q.quote_amount) FILTER (WHERE q.accepted_flag), 2) AS accepted_quote_value
FROM dim_dealer AS d
LEFT JOIN fact_quote AS q ON q.dealer_id = d.dealer_id
GROUP BY
    d.dealer_id,
    d.dealer_name,
    d.dealer_region,
    d.dealer_type,
    d.dealer_rating,
    d.active_flag;

CREATE OR REPLACE VIEW vw_monthly_commercial_performance AS
SELECT
    DATE_TRUNC('month', inquiry_date)::date AS month,
    COUNT(*) AS total_inquiries,
    COUNT(*) FILTER (WHERE conversion_flag) AS converted_inquiries,
    ROUND(AVG(conversion_flag::int), 4) AS conversion_rate,
    ROUND(AVG(final_sale_price) FILTER (WHERE conversion_flag), 2) AS average_sale_value,
    ROUND(AVG(quote_spread), 2) AS average_quote_spread,
    ROUND(AVG(fastest_response_hours), 2) AS average_fastest_response_hours
FROM fact_inquiry
GROUP BY DATE_TRUNC('month', inquiry_date)::date;

CREATE OR REPLACE VIEW vw_data_quality_summary AS
SELECT
    assessment_date,
    stage,
    metric_name,
    passed_records,
    total_records,
    rate,
    ROUND(rate * 100, 2) AS rate_percent,
    description
FROM data_quality_metrics;
