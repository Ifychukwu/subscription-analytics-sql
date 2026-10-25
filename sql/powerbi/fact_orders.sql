-- Power BI export: fact_orders, one row per box (order_id is unique).
-- Built from the raw table with the same cleaning as v_orders (de-duplicated, known customers,
-- revenue present) but KEEPING refunded boxes, flagged by status, so refund rate can be reported.
-- Margin uses the same assumptions as Q6: ingredients (cost per person × people) + £6.50 packaging/delivery.

WITH dedup AS (
    SELECT o.*,
           ROW_NUMBER() OVER (PARTITION BY o.order_id ORDER BY o.rowid) AS rn
    FROM fact_orders o
    JOIN dim_customers c ON c.customer_id = o.customer_id
),
clean AS (
    SELECT order_id, customer_id, delivery_date, plan_id, status, revenue_gbp, discount_gbp
    FROM dedup
    WHERE rn = 1 AND revenue_gbp IS NOT NULL
),
box_cost AS (
    SELECT i.order_id, SUM(r.ingredient_cost_gbp * p.people) AS ingredient_cost_gbp
    FROM fact_order_items i
    JOIN clean o USING (order_id)
    JOIN dim_recipes r USING (recipe_id)
    JOIN dim_plans p ON p.plan_id = o.plan_id
    GROUP BY i.order_id
),
first_box AS (
    SELECT customer_id, MIN(delivery_date) AS first_box_date
    FROM v_orders
    GROUP BY customer_id
)
SELECT o.order_id,
       o.customer_id,
       o.delivery_date,
       CAST(strftime('%Y%m%d', o.delivery_date) AS INTEGER)              AS date_key,
       o.plan_id,
       o.status,
       CASE WHEN o.status = 'delivered' THEN 1 ELSE 0 END                AS is_delivered,
       o.revenue_gbp,
       o.discount_gbp,
       ROUND(b.ingredient_cost_gbp, 2)                                   AS ingredient_cost_gbp,
       6.50                                                              AS fulfilment_cost_gbp,
       ROUND(o.revenue_gbp - b.ingredient_cost_gbp - 6.50, 2)            AS gross_margin_gbp,
       -- calendar months since the customer's first delivered box (same definition as Q4)
       (CAST(strftime('%Y', o.delivery_date) AS INT) - CAST(strftime('%Y', f.first_box_date) AS INT)) * 12
     + (CAST(strftime('%m', o.delivery_date) AS INT) - CAST(strftime('%m', f.first_box_date) AS INT))
                                                                         AS months_since_first_box
FROM clean o
LEFT JOIN box_cost b  USING (order_id)
LEFT JOIN first_box f USING (customer_id)
ORDER BY o.order_id;
