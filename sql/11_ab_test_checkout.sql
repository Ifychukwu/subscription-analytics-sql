-- Q11. Did the new one-page checkout (variant B) increase purchases? A two-proportion z-test in SQL.
-- Techniques: conditional aggregation, cross join of summary rows, sqrt() for the pooled standard error.
-- Metric: purchases / sessions that reached checkout (the step the variant changed).

WITH reached AS (
    SELECT session_id,
           MAX(ab_variant)                AS variant,
           MAX(event_name = 'checkout')   AS saw_checkout,
           MAX(event_name = 'purchase')   AS purchased
    FROM fact_events
    GROUP BY session_id
),
by_variant AS (
    SELECT variant,
           SUM(saw_checkout)                       AS n,
           SUM(purchased)                          AS conversions,
           1.0 * SUM(purchased) / SUM(saw_checkout) AS rate
    FROM reached
    WHERE saw_checkout = 1
    GROUP BY variant
),
test AS (
    SELECT a.n AS n_a, a.rate AS rate_a, b.n AS n_b, b.rate AS rate_b,
           (a.conversions + b.conversions) * 1.0 / (a.n + b.n) AS pooled
    FROM by_variant a CROSS JOIN by_variant b
    WHERE a.variant = 'A' AND b.variant = 'B'
)
SELECT n_a, ROUND(100 * rate_a, 2) AS conversion_a_pct,
       n_b, ROUND(100 * rate_b, 2) AS conversion_b_pct,
       ROUND(100 * (rate_b - rate_a) / rate_a, 1) AS relative_lift_pct,
       ROUND((rate_b - rate_a) / sqrt(pooled * (1 - pooled) * (1.0 / n_a + 1.0 / n_b)), 2) AS z_score,
       CASE WHEN abs((rate_b - rate_a) / sqrt(pooled * (1 - pooled) * (1.0 / n_a + 1.0 / n_b))) > 1.96
            THEN 'significant at 5%' ELSE 'not significant' END AS verdict
FROM test;
