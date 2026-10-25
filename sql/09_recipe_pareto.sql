-- Q9. Do a few recipes drive most demand? Pareto (80/20) analysis.
-- Techniques: running total with SUM() OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING), RANK().

WITH demand AS (
    SELECT r.recipe_id, r.recipe_name, r.cuisine, COUNT(*) AS times_ordered
    FROM fact_order_items i
    JOIN v_orders o USING (order_id)
    JOIN dim_recipes r USING (recipe_id)
    GROUP BY r.recipe_id
)
SELECT RANK() OVER (ORDER BY times_ordered DESC) AS rank,
       recipe_name,
       cuisine,
       times_ordered,
       ROUND(100.0 * times_ordered / SUM(times_ordered) OVER (), 2) AS share_pct,
       ROUND(100.0 * SUM(times_ordered) OVER (ORDER BY times_ordered DESC ROWS UNBOUNDED PRECEDING)
                   / SUM(times_ordered) OVER (), 1) AS cumulative_share_pct
FROM demand
ORDER BY times_ordered DESC;
