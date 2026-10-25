-- Q4. Do customers stick around? Monthly signup-cohort retention.
-- Techniques: cohort assignment, month-difference arithmetic, conditional aggregation, FIRST_VALUE.

WITH first_order AS (
    SELECT customer_id, MIN(delivery_date) AS first_date
    FROM v_orders
    GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT
           o.customer_id,
           strftime('%Y-%m', f.first_date) AS cohort,
           (CAST(strftime('%Y', o.delivery_date) AS INT) - CAST(strftime('%Y', f.first_date) AS INT)) * 12
         + (CAST(strftime('%m', o.delivery_date) AS INT) - CAST(strftime('%m', f.first_date) AS INT)) AS month_number
    FROM v_orders o
    JOIN first_order f USING (customer_id)
),
cohort_counts AS (
    SELECT cohort, month_number, COUNT(*) AS customers
    FROM activity
    GROUP BY cohort, month_number
)
SELECT cohort,
       month_number,
       customers,
       ROUND(100.0 * customers / FIRST_VALUE(customers) OVER (PARTITION BY cohort ORDER BY month_number), 1) AS retention_pct
FROM cohort_counts
WHERE month_number <= 12
ORDER BY cohort, month_number;
