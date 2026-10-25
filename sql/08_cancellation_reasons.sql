-- Q8. Why do customers cancel, and does it differ for early vs established customers?
-- Techniques: tenure bucketing with CASE, percentage of total within group via window SUM() OVER (PARTITION BY).

WITH tenure AS (
    SELECT x.customer_id,
           x.reason,
           COUNT(o.order_id) AS boxes_received
    FROM fact_cancellations x
    LEFT JOIN v_orders o ON o.customer_id = x.customer_id AND o.delivery_date <= x.cancel_date
    GROUP BY x.customer_id, x.reason
),
bucketed AS (
    SELECT CASE WHEN boxes_received <= 2 THEN '1. trialists (≤2 boxes)'
                WHEN boxes_received <= 8 THEN '2. early (3–8 boxes)'
                ELSE '3. established (9+ boxes)' END AS tenure_group,
           reason
    FROM tenure
)
SELECT tenure_group,
       reason,
       COUNT(*) AS cancellations,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY tenure_group), 1) AS pct_of_group
FROM bucketed
GROUP BY tenure_group, reason
ORDER BY tenure_group, cancellations DESC;
