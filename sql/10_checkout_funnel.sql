-- Q10. Where do visitors drop out of the sign-up funnel, by device?
-- Techniques: pivoting events to one row per session with MAX(CASE ...), step-to-step conversion.

WITH sessions AS (
    SELECT session_id,
           device,
           MAX(event_name = 'landing')     AS landing,
           MAX(event_name = 'menu')        AS menu,
           MAX(event_name = 'plan_select') AS plan_select,
           MAX(event_name = 'checkout')    AS checkout,
           MAX(event_name = 'purchase')    AS purchase
    FROM fact_events
    GROUP BY session_id, device
)
SELECT device,
       SUM(landing) AS sessions,
       ROUND(100.0 * SUM(menu)        / SUM(landing), 1)     AS landing_to_menu_pct,
       ROUND(100.0 * SUM(plan_select) / SUM(menu), 1)        AS menu_to_plan_pct,
       ROUND(100.0 * SUM(checkout)    / SUM(plan_select), 1) AS plan_to_checkout_pct,
       ROUND(100.0 * SUM(purchase)    / SUM(checkout), 1)    AS checkout_to_purchase_pct,
       ROUND(100.0 * SUM(purchase)    / SUM(landing), 2)     AS overall_conversion_pct
FROM sessions
GROUP BY device
ORDER BY sessions DESC;
