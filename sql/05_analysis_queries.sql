SET search_path TO automotive_analytics, public;

-- 01. Monthly inquiry volume and converted volume.
SELECT
    DATE_TRUNC('month', inquiry_date)::date AS month,
    COUNT(*) AS inquiries,
    COUNT(*) FILTER (WHERE conversion_flag) AS converted_inquiries
FROM fact_inquiry
GROUP BY 1
ORDER BY 1;

-- 02. Monthly conversion rate with a three-month rolling benchmark.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', inquiry_date)::date AS month,
        COUNT(*) AS inquiries,
        COUNT(*) FILTER (WHERE conversion_flag) AS conversions
    FROM fact_inquiry
    GROUP BY 1
)
SELECT
    month,
    inquiries,
    conversions,
    ROUND(conversions::numeric / NULLIF(inquiries, 0), 4) AS conversion_rate,
    ROUND(
        SUM(conversions) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)::numeric
        / NULLIF(SUM(inquiries) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0),
        4
    ) AS rolling_3m_conversion_rate
FROM monthly
ORDER BY month;

-- 03. Average quotation and accepted quotation by calendar month.
SELECT
    DATE_TRUNC('month', quote_date)::date AS month,
    ROUND(AVG(quote_amount), 2) AS average_quote,
    ROUND(AVG(quote_amount) FILTER (WHERE accepted_flag), 2) AS average_accepted_quote,
    COUNT(*) AS quote_count
FROM fact_quote
GROUP BY 1
ORDER BY 1;

-- 04. Average inquiry-level quotation spread by vehicle type.
SELECT
    v.vehicle_type,
    COUNT(*) AS inquiries,
    ROUND(AVG(i.quote_spread), 2) AS average_quote_spread_chf,
    ROUND(AVG(i.quote_spread_pct) * 100, 2) AS average_quote_spread_percent
FROM fact_inquiry AS i
JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id
GROUP BY v.vehicle_type
ORDER BY average_quote_spread_chf DESC;

-- 05. Median quotation overall and by brand using PostgreSQL percentiles.
SELECT
    v.brand,
    COUNT(*) AS quotes,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY q.quote_amount)::numeric, 2) AS median_quote,
    ROUND(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY q.quote_amount)::numeric, 2) AS p90_quote
FROM fact_quote AS q
JOIN fact_inquiry AS i ON i.inquiry_id = q.inquiry_id
JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id
GROUP BY v.brand
HAVING COUNT(*) >= 100
ORDER BY median_quote DESC;

-- 06. Dealer performance using wins, speed, competitiveness, and accepted value.
SELECT
    dealer_id,
    dealer_name,
    dealer_region,
    total_quotes,
    accepted_quotes,
    dealer_win_rate,
    average_response_time_hours,
    average_quote_to_market_ratio,
    accepted_quote_value
FROM vw_dealer_performance
WHERE total_quotes >= 250
ORDER BY dealer_win_rate DESC, accepted_quote_value DESC
LIMIT 20;

-- 07. Dealer win rate within region, ranked only among dealers with adequate volume.
WITH eligible AS (
    SELECT *
    FROM vw_dealer_performance
    WHERE total_quotes >= 250
), ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY dealer_region
            ORDER BY dealer_win_rate DESC, accepted_quote_value DESC
        ) AS regional_rank
    FROM eligible
)
SELECT *
FROM ranked
WHERE regional_rank <= 5
ORDER BY dealer_region, regional_rank;

-- 08. Conversion by fastest quote-response band at the inquiry grain.
SELECT
    CASE
        WHEN fastest_response_hours < 4 THEN '<4 hours'
        WHEN fastest_response_hours < 8 THEN '4-8 hours'
        WHEN fastest_response_hours < 16 THEN '8-16 hours'
        WHEN fastest_response_hours < 24 THEN '16-24 hours'
        ELSE '24+ hours'
    END AS response_band,
    COUNT(*) AS inquiries,
    ROUND(AVG(conversion_flag::int), 4) AS conversion_rate,
    ROUND(AVG(final_sale_price) FILTER (WHERE conversion_flag), 2) AS average_sale_value
FROM fact_inquiry
GROUP BY 1
ORDER BY MIN(fastest_response_hours);

-- 09. Lead source quality: volume, conversion, value, and response.
SELECT
    lead_source,
    COUNT(*) AS inquiries,
    COUNT(*) FILTER (WHERE conversion_flag) AS conversions,
    ROUND(AVG(conversion_flag::int), 4) AS conversion_rate,
    ROUND(AVG(final_sale_price) FILTER (WHERE conversion_flag), 2) AS average_sale_value,
    ROUND(AVG(fastest_response_hours), 2) AS average_fastest_response_hours
FROM fact_inquiry
GROUP BY lead_source
ORDER BY conversion_rate DESC;

-- 10. Conversion and commercial value by vehicle brand.
SELECT
    v.brand,
    COUNT(*) AS inquiries,
    ROUND(AVG(i.conversion_flag::int), 4) AS conversion_rate,
    ROUND(AVG(v.estimated_market_value), 2) AS average_market_value,
    ROUND(SUM(i.final_sale_price) FILTER (WHERE i.conversion_flag), 2) AS accepted_value
FROM fact_inquiry AS i
JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id
GROUP BY v.brand
HAVING COUNT(*) >= 500
ORDER BY accepted_value DESC;

-- 11. Conversion and quote dispersion by vehicle age.
SELECT
    CASE
        WHEN vehicle_age_at_inquiry <= 2 THEN '0-2 years'
        WHEN vehicle_age_at_inquiry <= 5 THEN '3-5 years'
        WHEN vehicle_age_at_inquiry <= 9 THEN '6-9 years'
        ELSE '10+ years'
    END AS vehicle_age_band,
    COUNT(*) AS inquiries,
    ROUND(AVG(conversion_flag::int), 4) AS conversion_rate,
    ROUND(AVG(quote_spread), 2) AS average_quote_spread,
    ROUND(AVG(quote_spread_pct) * 100, 2) AS average_quote_spread_percent
FROM fact_inquiry
GROUP BY 1
ORDER BY MIN(vehicle_age_at_inquiry);

-- 12. Conversion by mileage bracket with correct inquiry denominator.
SELECT
    v.mileage_bracket,
    COUNT(*) AS inquiries,
    ROUND(AVG(i.conversion_flag::int), 4) AS conversion_rate,
    ROUND(AVG(i.quote_spread), 2) AS average_quote_spread
FROM fact_inquiry AS i
JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id
GROUP BY v.mileage_bracket
ORDER BY MIN(v.mileage_km);

-- 13. Quote competitiveness by dealer, excluding explicitly flagged anomalies.
SELECT
    d.dealer_id,
    d.dealer_name,
    COUNT(*) AS valid_quotes,
    ROUND(AVG(q.quote_to_market_ratio), 4) AS average_quote_to_market_ratio,
    ROUND(AVG(q.response_time_hours), 2) AS average_response_hours,
    ROUND(AVG(q.accepted_flag::int), 4) AS quote_win_rate
FROM fact_quote AS q
JOIN dim_dealer AS d ON d.dealer_id = q.dealer_id
WHERE NOT q.anomaly_flag
GROUP BY d.dealer_id, d.dealer_name
HAVING COUNT(*) >= 250
ORDER BY average_quote_to_market_ratio DESC, quote_win_rate DESC;

-- 14. Vehicle-segment opportunity matrix.
SELECT
    v.vehicle_type,
    v.fuel_type,
    COUNT(*) AS inquiries,
    ROUND(AVG(i.conversion_flag::int), 4) AS conversion_rate,
    ROUND(AVG(v.estimated_market_value), 2) AS average_market_value,
    ROUND(SUM(i.final_sale_price) FILTER (WHERE i.conversion_flag), 2) AS accepted_value
FROM fact_inquiry AS i
JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id
GROUP BY v.vehicle_type, v.fuel_type
HAVING COUNT(*) >= 100
ORDER BY accepted_value DESC;

-- 15. Dealer-region performance.
SELECT
    d.dealer_region,
    COUNT(q.quote_id) AS quotes,
    COUNT(q.quote_id) FILTER (WHERE q.accepted_flag) AS wins,
    ROUND(AVG(q.accepted_flag::int), 4) AS quote_win_rate,
    ROUND(AVG(q.response_time_hours), 2) AS average_response_hours,
    ROUND(SUM(q.quote_amount) FILTER (WHERE q.accepted_flag), 2) AS accepted_value
FROM fact_quote AS q
JOIN dim_dealer AS d ON d.dealer_id = q.dealer_id
GROUP BY d.dealer_region
ORDER BY accepted_value DESC;

-- 16. Month-over-month inquiry growth with LAG.
WITH monthly AS (
    SELECT DATE_TRUNC('month', inquiry_date)::date AS month, COUNT(*) AS inquiries
    FROM fact_inquiry
    GROUP BY 1
), compared AS (
    SELECT
        month,
        inquiries,
        LAG(inquiries) OVER (ORDER BY month) AS previous_month_inquiries
    FROM monthly
)
SELECT
    month,
    inquiries,
    previous_month_inquiries,
    ROUND(
        (inquiries - previous_month_inquiries)::numeric
        / NULLIF(previous_month_inquiries, 0),
        4
    ) AS month_over_month_growth
FROM compared
ORDER BY month;

-- 17. Year-over-year inquiry and conversion growth by calendar month.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', inquiry_date)::date AS month,
        COUNT(*) AS inquiries,
        COUNT(*) FILTER (WHERE conversion_flag) AS conversions
    FROM fact_inquiry
    GROUP BY 1
), compared AS (
    SELECT
        *,
        LAG(inquiries, 12) OVER (ORDER BY month) AS prior_year_inquiries,
        LAG(conversions, 12) OVER (ORDER BY month) AS prior_year_conversions
    FROM monthly
)
SELECT
    month,
    inquiries,
    ROUND((inquiries - prior_year_inquiries)::numeric / NULLIF(prior_year_inquiries, 0), 4) AS inquiry_yoy_growth,
    conversions,
    ROUND((conversions - prior_year_conversions)::numeric / NULLIF(prior_year_conversions, 0), 4) AS conversion_yoy_growth
FROM compared
ORDER BY month;

-- 18. Composite dealer ranking with percentile-based component scores.
WITH eligible AS (
    SELECT * FROM vw_dealer_performance WHERE total_quotes >= 250
), scored AS (
    SELECT
        *,
        PERCENT_RANK() OVER (ORDER BY dealer_win_rate) AS win_score,
        1 - PERCENT_RANK() OVER (ORDER BY average_response_time_hours) AS speed_score,
        PERCENT_RANK() OVER (ORDER BY average_quote_to_market_ratio) AS competitiveness_score
    FROM eligible
)
SELECT
    dealer_id,
    dealer_name,
    dealer_region,
    total_quotes,
    dealer_win_rate,
    average_response_time_hours,
    average_quote_to_market_ratio,
    ROUND((0.50 * win_score + 0.25 * speed_score + 0.25 * competitiveness_score)::numeric, 4) AS composite_score,
    RANK() OVER (
        ORDER BY 0.50 * win_score + 0.25 * speed_score + 0.25 * competitiveness_score DESC
    ) AS dealer_rank
FROM scored
ORDER BY dealer_rank;

-- 19. Robust quote outlier detection using global IQR plus business ratio flag.
WITH bounds AS (
    SELECT
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY quote_to_market_ratio) AS q1,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY quote_to_market_ratio) AS q3
    FROM fact_quote
), flagged AS (
    SELECT
        q.*,
        b.q1,
        b.q3,
        (b.q3 - b.q1) AS iqr
    FROM fact_quote AS q
    CROSS JOIN bounds AS b
)
SELECT
    quote_id,
    inquiry_id,
    dealer_id,
    quote_amount,
    estimated_market_value,
    quote_to_market_ratio,
    anomaly_flag,
    CASE
        WHEN quote_to_market_ratio < q1 - 1.5 * iqr THEN 'IQR low outlier'
        WHEN quote_to_market_ratio > q3 + 1.5 * iqr THEN 'IQR high outlier'
        WHEN anomaly_flag THEN 'Business-rule anomaly'
    END AS anomaly_reason
FROM flagged
WHERE anomaly_flag
   OR quote_to_market_ratio < q1 - 1.5 * iqr
   OR quote_to_market_ratio > q3 + 1.5 * iqr
ORDER BY ABS(quote_to_market_ratio - 1) DESC;

-- 20. Raw-versus-processed data-quality scorecard.
SELECT
    stage,
    metric_name,
    passed_records,
    total_records,
    ROUND(rate * 100, 2) AS rate_percent,
    ROUND(
        (
            rate - LAG(rate) OVER (
                PARTITION BY metric_name
                ORDER BY CASE stage WHEN 'Raw' THEN 1 WHEN 'Processed' THEN 2 END
            )
        ) * 100,
        2
    ) AS improvement_percentage_points
FROM data_quality_metrics
ORDER BY
    metric_name,
    CASE stage WHEN 'Raw' THEN 1 WHEN 'Processed' THEN 2 END;

-- 21. Quote-spread growth by single year of vehicle age with volume guardrail.
SELECT
    vehicle_age_at_inquiry,
    COUNT(*) AS inquiries,
    ROUND(AVG(quote_spread), 2) AS average_spread,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY quote_spread)::numeric, 2) AS median_spread,
    ROUND(AVG(quote_spread_pct) * 100, 2) AS average_spread_percent
FROM fact_inquiry
GROUP BY vehicle_age_at_inquiry
HAVING COUNT(*) >= 100
ORDER BY vehicle_age_at_inquiry;

-- 22. Lead-source efficiency index relative to the portfolio average.
WITH source_metrics AS (
    SELECT
        lead_source,
        COUNT(*) AS inquiries,
        AVG(conversion_flag::int) AS conversion_rate,
        AVG(final_sale_price) FILTER (WHERE conversion_flag) AS average_sale_value
    FROM fact_inquiry
    GROUP BY lead_source
), portfolio AS (
    SELECT
        AVG(conversion_flag::int) AS conversion_rate,
        AVG(final_sale_price) FILTER (WHERE conversion_flag) AS average_sale_value
    FROM fact_inquiry
)
SELECT
    s.lead_source,
    s.inquiries,
    ROUND(s.conversion_rate, 4) AS conversion_rate,
    ROUND(s.average_sale_value, 2) AS average_sale_value,
    ROUND((s.conversion_rate / p.conversion_rate) * (s.average_sale_value / p.average_sale_value), 4) AS quality_index
FROM source_metrics AS s
CROSS JOIN portfolio AS p
ORDER BY quality_index DESC;

-- 23. Conversion by response-time quartile using NTILE at inquiry grain.
WITH bucketed AS (
    SELECT
        inquiry_id,
        conversion_flag,
        fastest_response_hours,
        NTILE(4) OVER (ORDER BY fastest_response_hours) AS response_quartile
    FROM fact_inquiry
)
SELECT
    response_quartile,
    COUNT(*) AS inquiries,
    ROUND(MIN(fastest_response_hours), 2) AS min_hours,
    ROUND(MAX(fastest_response_hours), 2) AS max_hours,
    ROUND(AVG(conversion_flag::int), 4) AS conversion_rate
FROM bucketed
GROUP BY response_quartile
ORDER BY response_quartile;

-- 24. Highest-value model opportunities with rank inside brand.
WITH model_metrics AS (
    SELECT
        v.brand,
        v.model,
        COUNT(*) AS inquiries,
        AVG(v.estimated_market_value) AS average_market_value,
        AVG(i.conversion_flag::int) AS conversion_rate,
        SUM(i.final_sale_price) FILTER (WHERE i.conversion_flag) AS accepted_value
    FROM fact_inquiry AS i
    JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id
    GROUP BY v.brand, v.model
    HAVING COUNT(*) >= 250
), ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY brand ORDER BY accepted_value DESC) AS model_rank
    FROM model_metrics
)
SELECT
    brand,
    model,
    inquiries,
    ROUND(average_market_value, 2) AS average_market_value,
    ROUND(conversion_rate, 4) AS conversion_rate,
    ROUND(accepted_value, 2) AS accepted_value,
    model_rank
FROM ranked
WHERE model_rank <= 3
ORDER BY accepted_value DESC;
