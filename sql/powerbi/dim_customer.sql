-- Power BI export: dim_customer, one row per customer.
-- Adds cohort (month of first delivered box), cancellation info and the RFM segment from Q7,
-- so the dashboard can slice by them without re-implementing the logic in DAX.
-- Requires the v_orders view (sql/02_clean_orders_view.sql).

WITH first_box AS (
    SELECT customer_id, MIN(delivery_date) AS first_box_date
    FROM v_orders
    GROUP BY customer_id
),
rfm_base AS (                                   -- same rules as sql/07_rfm_segmentation.sql
    SELECT customer_id,
           julianday('2026-06-29') - julianday(MAX(delivery_date)) AS recency_days,
           COUNT(*) AS frequency,
           SUM(revenue_gbp) AS monetary_gbp
    FROM v_orders
    GROUP BY customer_id
),
rfm AS (                                        -- keep all three windows, in Q7's order, so NTILE
    SELECT *,                                   -- breaks ties the same way and segments match Q7 exactly
           NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
           NTILE(5) OVER (ORDER BY frequency)          AS f_score,
           NTILE(5) OVER (ORDER BY monetary_gbp)       AS m_score
    FROM rfm_base
),
cancel AS (
    SELECT customer_id, MIN(cancel_date) AS cancel_date, MIN(reason) AS cancel_reason
    FROM fact_cancellations
    GROUP BY customer_id
)
SELECT c.customer_id,
       c.signup_date,
       CAST(strftime('%Y%m%d', c.signup_date) AS INTEGER)               AS signup_date_key,
       c.region,
       ch.channel_id,
       c.plan_id                                                        AS signup_plan_id,
       c.age_band,
       f.first_box_date,
       CASE WHEN f.first_box_date IS NOT NULL
            THEN strftime('%Y-%m-01', f.first_box_date) END              AS cohort_month,
       x.cancel_date,
       CASE WHEN x.customer_id IS NULL THEN 0 ELSE 1 END                AS has_cancelled,
       CASE
           WHEN r.customer_id IS NULL               THEN 'No delivered boxes'
           WHEN r.r_score >= 4 AND r.f_score >= 4   THEN 'Champions'
           WHEN r.r_score >= 3 AND r.f_score >= 3   THEN 'Loyal'
           WHEN r.r_score >= 4 AND r.f_score <= 2   THEN 'New / promising'
           WHEN r.r_score = 2 AND r.f_score >= 3    THEN 'At risk'
           WHEN r.r_score = 1 AND r.f_score >= 3    THEN 'Lost high-value'
           ELSE 'Low engagement'
       END                                                              AS rfm_segment
FROM dim_customers c
JOIN tmp_channel ch ON ch.channel_code = c.acquisition_channel
LEFT JOIN first_box f USING (customer_id)
LEFT JOIN rfm r       USING (customer_id)
LEFT JOIN cancel x    USING (customer_id)
ORDER BY c.customer_id;
