-- Q15. Make a slow dashboard query fast: add a covering index and compare query plans.
-- Techniques: EXPLAIN QUERY PLAN, composite index design, timing in the runner (see results/15_*.csv).
-- The runner executes this file twice: without and with the index below.

-- @index: CREATE INDEX IF NOT EXISTS idx_orders_customer_date ON fact_orders(customer_id, delivery_date, revenue_gbp);

SELECT customer_id, MAX(delivery_date) AS last_box, SUM(revenue_gbp) AS spend_gbp
FROM fact_orders
WHERE customer_id BETWEEN 5000 AND 5200
GROUP BY customer_id;
