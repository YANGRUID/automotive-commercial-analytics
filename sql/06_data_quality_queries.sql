SET search_path TO automotive_analytics, public;

-- 01. Primary-key uniqueness checks. Every duplicate count must be zero.
SELECT 'dim_customer.customer_id' AS rule, COUNT(*) - COUNT(DISTINCT customer_id) AS failures FROM dim_customer
UNION ALL
SELECT 'dim_vehicle.vehicle_id', COUNT(*) - COUNT(DISTINCT vehicle_id) FROM dim_vehicle
UNION ALL
SELECT 'dim_dealer.dealer_id', COUNT(*) - COUNT(DISTINCT dealer_id) FROM dim_dealer
UNION ALL
SELECT 'fact_inquiry.inquiry_id', COUNT(*) - COUNT(DISTINCT inquiry_id) FROM fact_inquiry
UNION ALL
SELECT 'fact_quote.quote_id', COUNT(*) - COUNT(DISTINCT quote_id) FROM fact_quote;

-- 02. Vehicle mileage validity.
SELECT COUNT(*) AS invalid_mileage_rows
FROM dim_vehicle
WHERE mileage_km NOT BETWEEN 0 AND 500000 OR mileage_km IS NULL;

-- 03. Quote monetary validity.
SELECT COUNT(*) AS invalid_quote_amount_rows
FROM fact_quote
WHERE quote_amount <= 0 OR quote_amount > 500000 OR quote_amount IS NULL;

-- 04. Inquiry foreign-key coverage (should be guaranteed by constraints).
SELECT
    COUNT(*) FILTER (WHERE c.customer_id IS NULL) AS orphan_customers,
    COUNT(*) FILTER (WHERE v.vehicle_id IS NULL) AS orphan_vehicles
FROM fact_inquiry AS i
LEFT JOIN dim_customer AS c ON c.customer_id = i.customer_id
LEFT JOIN dim_vehicle AS v ON v.vehicle_id = i.vehicle_id;

-- 05. Quote foreign-key coverage.
SELECT
    COUNT(*) FILTER (WHERE i.inquiry_id IS NULL) AS orphan_inquiries,
    COUNT(*) FILTER (WHERE d.dealer_id IS NULL) AS orphan_dealers
FROM fact_quote AS q
LEFT JOIN fact_inquiry AS i ON i.inquiry_id = q.inquiry_id
LEFT JOIN dim_dealer AS d ON d.dealer_id = q.dealer_id;

-- 06. Impossible quote/inquiry date sequence.
SELECT COUNT(*) AS quote_before_inquiry_rows
FROM fact_quote AS q
JOIN fact_inquiry AS i ON i.inquiry_id = q.inquiry_id
WHERE q.quote_date < i.inquiry_date;

-- 07. One accepted quote for each converted inquiry and none otherwise.
WITH accepted AS (
    SELECT inquiry_id, COUNT(*) FILTER (WHERE accepted_flag) AS accepted_count
    FROM fact_quote
    GROUP BY inquiry_id
)
SELECT COUNT(*) AS invalid_accepted_quote_rules
FROM fact_inquiry AS i
JOIN accepted AS a ON a.inquiry_id = i.inquiry_id
WHERE (i.conversion_flag AND a.accepted_count <> 1)
   OR (NOT i.conversion_flag AND a.accepted_count <> 0);

-- 08. Winning dealer must equal the accepted quote dealer.
SELECT COUNT(*) AS winning_dealer_mismatches
FROM fact_inquiry AS i
JOIN fact_quote AS q
  ON q.inquiry_id = i.inquiry_id
 AND q.accepted_flag
WHERE i.winning_dealer_id IS DISTINCT FROM q.dealer_id;

-- 09. Recompute persisted inquiry quote metrics and show discrepancies.
WITH recomputed AS (
    SELECT
        inquiry_id,
        COUNT(*) AS quote_count,
        MAX(quote_amount) AS highest_quote,
        MIN(quote_amount) AS lowest_quote
    FROM fact_quote
    GROUP BY inquiry_id
)
SELECT COUNT(*) AS metric_discrepancies
FROM fact_inquiry AS i
JOIN recomputed AS r ON r.inquiry_id = i.inquiry_id
WHERE i.quote_count <> r.quote_count
   OR i.highest_quote <> r.highest_quote
   OR i.lowest_quote <> r.lowest_quote
   OR i.quote_spread <> r.highest_quote - r.lowest_quote;

-- 10. Operational issue and quarantine summary.
SELECT
    l.table_name,
    l.issue_type,
    l.affected_rows,
    l.action,
    COUNT(q.quarantine_id) AS quarantined_rows
FROM data_quality_issue_log AS l
LEFT JOIN quarantined_records AS q
  ON q.table_name = l.table_name
 AND q.issue_type = l.issue_type
GROUP BY l.table_name, l.issue_type, l.affected_rows, l.action
ORDER BY l.affected_rows DESC;
