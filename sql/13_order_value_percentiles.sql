-- Q13. What does a typical customer spend? Spend percentiles without a PERCENTILE function.
-- Techniques: PERCENT_RANK() / CUME_DIST() windows, picking the first row past each percentile.

WITH spend AS (
    SELECT customer_id, SUM(revenue_gbp) AS total_spend_gbp
    FROM v_orders
    GROUP BY customer_id
),
ranked AS (
    SELECT total_spend_gbp, CUME_DIST() OVER (ORDER BY total_spend_gbp) AS cd
    FROM spend
)
SELECT p.percentile,
       (SELECT ROUND(MIN(total_spend_gbp), 2) FROM ranked WHERE cd >= p.percentile / 100.0) AS spend_gbp
FROM (SELECT 10 AS percentile UNION ALL SELECT 25 UNION ALL SELECT 50 UNION ALL SELECT 75
      UNION ALL SELECT 90 UNION ALL SELECT 99) p
ORDER BY p.percentile;
