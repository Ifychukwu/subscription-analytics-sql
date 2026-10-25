-- Power BI export: fact_order_items, one row per recipe in a box (order_id + recipe_id is unique).
-- Carries date_key, customer_id and is_delivered so it joins straight to the dimensions
-- (star schema; no fact-to-fact relationship needed). Only boxes present in fact_orders are kept.

WITH dedup AS (
    SELECT o.order_id, o.customer_id, o.delivery_date, o.plan_id, o.status, o.revenue_gbp,
           ROW_NUMBER() OVER (PARTITION BY o.order_id ORDER BY o.rowid) AS rn
    FROM fact_orders o
    JOIN dim_customers c ON c.customer_id = o.customer_id
),
clean AS (
    SELECT * FROM dedup WHERE rn = 1 AND revenue_gbp IS NOT NULL
)
SELECT i.order_id,
       i.recipe_id,
       o.customer_id,
       CAST(strftime('%Y%m%d', o.delivery_date) AS INTEGER)   AS date_key,
       CASE WHEN o.status = 'delivered' THEN 1 ELSE 0 END     AS is_delivered,
       ROUND(r.ingredient_cost_gbp * p.people, 2)             AS ingredient_cost_gbp
FROM fact_order_items i
JOIN clean o       USING (order_id)
JOIN dim_recipes r USING (recipe_id)
JOIN dim_plans p   ON p.plan_id = o.plan_id
ORDER BY i.order_id, i.recipe_id;
