-- Q14. Is there a winter peak, and does it differ by region? Seasonal index per region.
-- Techniques: averages of averages, ratio to the region's own mean, AVG() OVER (PARTITION BY).

WITH weekly AS (
    SELECT c.region, o.delivery_date, COUNT(*) AS boxes
    FROM v_orders o
    JOIN dim_customers c USING (customer_id)
    WHERE o.delivery_date >= '2025-01-01' AND o.delivery_date < '2026-01-01'
    GROUP BY c.region, o.delivery_date
),
monthly AS (
    SELECT region, CAST(strftime('%m', delivery_date) AS INT) AS month, AVG(boxes) AS avg_weekly_boxes
    FROM weekly
    GROUP BY region, month
)
SELECT region, month,
       ROUND(avg_weekly_boxes, 1) AS avg_weekly_boxes,
       ROUND(avg_weekly_boxes / AVG(avg_weekly_boxes) OVER (PARTITION BY region), 3) AS seasonal_index
FROM monthly
ORDER BY region, month;
