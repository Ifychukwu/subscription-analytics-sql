-- Q1. Can we trust the data? Run quality checks before any analysis.
-- Techniques: UNION ALL of checks, anti-joins (LEFT JOIN ... IS NULL), GROUP BY ... HAVING for duplicates.

SELECT 'duplicate order rows' AS check_name,
       COUNT(*) AS failing_rows
FROM (
    SELECT order_id
    FROM fact_orders
    GROUP BY order_id
    HAVING COUNT(*) > 1
)
UNION ALL
SELECT 'orders with missing revenue', COUNT(*)
FROM fact_orders
WHERE revenue_gbp IS NULL
UNION ALL
SELECT 'orders for unknown customers', COUNT(*)
FROM fact_orders o
LEFT JOIN dim_customers c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL
UNION ALL
SELECT 'order items for unknown recipes', COUNT(*)
FROM fact_order_items i
LEFT JOIN dim_recipes r ON r.recipe_id = i.recipe_id
WHERE r.recipe_id IS NULL
UNION ALL
SELECT 'deliveries before signup', COUNT(*)
FROM fact_orders o
JOIN dim_customers c ON c.customer_id = o.customer_id
WHERE o.delivery_date < c.signup_date
UNION ALL
SELECT 'cancellations before signup', COUNT(*)
FROM fact_cancellations x
JOIN dim_customers c ON c.customer_id = x.customer_id
WHERE x.cancel_date < c.signup_date;
