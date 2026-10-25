-- Q6. Is each channel profitable? Customer lifetime value (gross margin) vs acquisition cost.
-- Techniques: joining facts at different grains (orders, items, marketing) via separate aggregates first.

WITH box_cost AS (
    SELECT i.order_id, SUM(r.ingredient_cost_gbp * p.people) AS ingredients_gbp
    FROM fact_order_items i
    JOIN dim_recipes r USING (recipe_id)
    JOIN v_orders o USING (order_id)
    JOIN dim_plans p ON p.plan_id = o.plan_id
    GROUP BY i.order_id
),
customer_value AS (
    SELECT c.acquisition_channel,
           o.customer_id,
           SUM(o.revenue_gbp)                                   AS revenue_gbp,
           SUM(o.revenue_gbp - b.ingredients_gbp - 6.50)        AS gross_margin_gbp   -- £6.50 packaging + delivery per box
    FROM v_orders o
    JOIN box_cost b USING (order_id)
    JOIN dim_customers c USING (customer_id)
    GROUP BY c.acquisition_channel, o.customer_id
),
spend AS (
    SELECT channel AS acquisition_channel, SUM(spend_gbp) AS spend_gbp
    FROM fact_marketing
    GROUP BY channel
),
signups AS (
    SELECT acquisition_channel, COUNT(*) AS customers
    FROM dim_customers
    GROUP BY acquisition_channel
)
SELECT v.acquisition_channel,
       s.customers,
       ROUND(AVG(v.revenue_gbp), 2)                       AS revenue_per_customer_gbp,
       ROUND(SUM(v.gross_margin_gbp) / s.customers, 2)     AS margin_per_customer_gbp,
       ROUND(sp.spend_gbp / s.customers, 2)                AS cac_gbp,
       ROUND((SUM(v.gross_margin_gbp) / s.customers) / (sp.spend_gbp / s.customers), 2) AS ltv_to_cac
FROM customer_value v
JOIN signups s USING (acquisition_channel)
JOIN spend sp USING (acquisition_channel)
GROUP BY v.acquisition_channel
ORDER BY ltv_to_cac DESC;
