-- Q2. Create a clean, de-duplicated orders view that every later query uses.
-- Techniques: CREATE VIEW, ROW_NUMBER() window for de-duplication, filtering orphans and nulls.

DROP VIEW IF EXISTS v_orders;
CREATE VIEW v_orders AS
WITH ranked AS (
    SELECT o.*,
           ROW_NUMBER() OVER (PARTITION BY o.order_id ORDER BY o.rowid) AS rn
    FROM fact_orders o
    JOIN dim_customers c ON c.customer_id = o.customer_id      -- drop orphans
)
SELECT order_id, customer_id, delivery_date, plan_id, status, revenue_gbp, discount_gbp
FROM ranked
WHERE rn = 1                     -- drop duplicates
  AND revenue_gbp IS NOT NULL    -- drop rows with missing revenue
  AND status = 'delivered';      -- refunds don't count as revenue

SELECT
    (SELECT COUNT(*) FROM fact_orders) AS raw_rows,
    (SELECT COUNT(*) FROM v_orders)    AS clean_delivered_rows,
    (SELECT COUNT(*) FROM fact_orders WHERE status = 'refunded') AS refunded_rows;
