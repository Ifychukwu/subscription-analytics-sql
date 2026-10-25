-- Q7. Who are our best customers? RFM (recency, frequency, monetary) segmentation.
-- Techniques: NTILE() quintiles, CASE-based segment rules, julianday date arithmetic.

WITH base AS (
    SELECT customer_id,
           julianday('2026-06-29') - julianday(MAX(delivery_date)) AS recency_days,
           COUNT(*)                                               AS frequency,
           SUM(revenue_gbp)                                       AS monetary_gbp
    FROM v_orders
    GROUP BY customer_id
),
scored AS (
    SELECT *,
           NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,   -- 5 = most recent
           NTILE(5) OVER (ORDER BY frequency)          AS f_score,
           NTILE(5) OVER (ORDER BY monetary_gbp)       AS m_score
    FROM base
),
segmented AS (
    SELECT *,
           CASE
               WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
               WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal'
               WHEN r_score >= 4 AND f_score <= 2 THEN 'New / promising'
               WHEN r_score = 2 AND f_score >= 3  THEN 'At risk'
               WHEN r_score = 1 AND f_score >= 3  THEN 'Lost high-value'
               ELSE 'Low engagement'
           END AS segment
    FROM scored
)
SELECT segment,
       COUNT(*)                                   AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)               AS pct_customers,
       ROUND(SUM(monetary_gbp), 0)                AS revenue_gbp,
       ROUND(100.0 * SUM(monetary_gbp) / SUM(SUM(monetary_gbp)) OVER (), 1) AS pct_revenue,
       ROUND(AVG(recency_days), 0)                AS avg_days_since_last_box,
       ROUND(AVG(frequency), 1)                   AS avg_boxes
FROM segmented
GROUP BY segment
ORDER BY revenue_gbp DESC;
