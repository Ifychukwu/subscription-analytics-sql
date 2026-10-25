-- Q12. Rebuild sessions from raw events: a "gaps and islands" problem.
-- A new session starts when a visitor is inactive for more than 30 minutes.
-- Techniques: LAG() to find gaps, running SUM() of "new session" flags to number the islands.

WITH ordered AS (
    SELECT visitor_id, event_time, event_name,
           (julianday(event_time) - julianday(LAG(event_time) OVER (PARTITION BY visitor_id ORDER BY event_time))) * 24 * 60
               AS minutes_since_prev
    FROM fact_events
),
flagged AS (
    SELECT *,
           CASE WHEN minutes_since_prev IS NULL OR minutes_since_prev > 30 THEN 1 ELSE 0 END AS new_session
    FROM ordered
),
numbered AS (
    SELECT *,
           SUM(new_session) OVER (PARTITION BY visitor_id ORDER BY event_time ROWS UNBOUNDED PRECEDING) AS session_no
    FROM flagged
),
sessions AS (
    SELECT visitor_id, session_no,
           MIN(event_time) AS started, MAX(event_time) AS ended, COUNT(*) AS events,
           MAX(event_name = 'purchase') AS purchased
    FROM numbered
    GROUP BY visitor_id, session_no
)
SELECT COUNT(*)                                                  AS reconstructed_sessions,
       (SELECT COUNT(DISTINCT session_id) FROM fact_events)      AS logged_sessions,
       ROUND(AVG(events), 2)                                     AS avg_events_per_session,
       ROUND(AVG((julianday(ended) - julianday(started)) * 24 * 60), 1) AS avg_minutes,
       ROUND(100.0 * AVG(purchased), 2)                          AS purchase_rate_pct
FROM sessions;
