-- Power BI export: fact_web_sessions, one row per web session (session_id is unique),
-- with 0/1 flags for each funnel step reached (the pivot used in Q10 and Q11).

SELECT session_id,
       MAX(visitor_id)                              AS visitor_id,
       MIN(event_time)                              AS session_start,
       CAST(strftime('%Y%m%d', MIN(event_time)) AS INTEGER) AS date_key,
       MAX(device)                                  AS device,
       MAX(ab_variant)                              AS ab_variant,
       MAX(event_name = 'landing')                  AS reached_landing,
       MAX(event_name = 'menu')                     AS reached_menu,
       MAX(event_name = 'plan_select')              AS reached_plan_select,
       MAX(event_name = 'checkout')                 AS reached_checkout,
       MAX(event_name = 'purchase')                 AS purchased
FROM fact_events
GROUP BY session_id
ORDER BY session_id;
