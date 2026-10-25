-- Q5. Which acquisition channels bring customers who stay? Month-3 and month-6 retention by channel.
-- Techniques: CTE reuse, conditional aggregation with FILTER, only counting cohorts old enough to be measured.

WITH first_order AS (
    SELECT customer_id, MIN(delivery_date) AS first_date
    FROM v_orders
    GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT o.customer_id,
           (julianday(o.delivery_date) - julianday(f.first_date)) / 30.44 AS months_since_first
    FROM v_orders o
    JOIN first_order f USING (customer_id)
),
per_customer AS (
    SELECT f.customer_id,
           c.acquisition_channel,
           f.first_date,
           MAX(a.months_since_first >= 3 AND a.months_since_first < 4) AS active_m3,
           MAX(a.months_since_first >= 6 AND a.months_since_first < 7) AS active_m6
    FROM first_order f
    JOIN dim_customers c USING (customer_id)
    JOIN activity a USING (customer_id)
    GROUP BY f.customer_id
)
SELECT acquisition_channel,
       COUNT(*) AS customers,
       ROUND(100.0 * AVG(active_m3) FILTER (WHERE first_date <= '2026-02-28'), 1) AS retained_month_3_pct,
       ROUND(100.0 * AVG(active_m6) FILTER (WHERE first_date <= '2025-11-30'), 1) AS retained_month_6_pct
FROM per_customer
GROUP BY acquisition_channel
ORDER BY retained_month_6_pct DESC;
