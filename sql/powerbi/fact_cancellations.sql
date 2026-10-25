-- Power BI export: fact_cancellations, one row per cancellation, with the tenure group used in Q8.

WITH tenure AS (
    SELECT x.customer_id, x.cancel_date, x.reason, COUNT(o.order_id) AS boxes_received
    FROM fact_cancellations x
    LEFT JOIN v_orders o ON o.customer_id = x.customer_id AND o.delivery_date <= x.cancel_date
    GROUP BY x.customer_id, x.cancel_date, x.reason
)
SELECT customer_id,
       cancel_date,
       CAST(strftime('%Y%m%d', cancel_date) AS INTEGER) AS date_key,
       reason,
       boxes_received,
       CASE WHEN boxes_received <= 2 THEN '1. Trialists (<=2 boxes)'
            WHEN boxes_received <= 8 THEN '2. Early (3-8 boxes)'
            ELSE '3. Established (9+ boxes)' END AS tenure_group
FROM tenure
ORDER BY customer_id;
