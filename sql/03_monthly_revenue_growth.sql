-- Q3. How is revenue trending? Month-on-month and year-on-year growth.
-- Techniques: date truncation with strftime, LAG() window function, NULLIF to avoid division by zero.

WITH monthly AS (
    SELECT strftime('%Y-%m', delivery_date) AS month,
           ROUND(SUM(revenue_gbp), 2)        AS revenue_gbp,
           COUNT(DISTINCT customer_id)       AS active_customers,
           COUNT(*)                          AS boxes
    FROM v_orders
    GROUP BY 1
)
SELECT month,
       revenue_gbp,
       active_customers,
       boxes,
       ROUND(revenue_gbp / boxes, 2) AS avg_box_value_gbp,
       ROUND(100.0 * (revenue_gbp - LAG(revenue_gbp, 1) OVER w) / NULLIF(LAG(revenue_gbp, 1) OVER w, 0), 1)  AS mom_growth_pct,
       ROUND(100.0 * (revenue_gbp - LAG(revenue_gbp, 12) OVER w) / NULLIF(LAG(revenue_gbp, 12) OVER w, 0), 1) AS yoy_growth_pct
FROM monthly
WINDOW w AS (ORDER BY month)
ORDER BY month;
