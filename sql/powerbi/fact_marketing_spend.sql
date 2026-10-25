-- Power BI export: fact_marketing_spend, one row per channel per month.
-- Monthly grain: date_key points at the first day of the month in dim_date.

SELECT m.month || '-01'                                         AS month_start_date,
       CAST(replace(m.month, '-', '') || '01' AS INTEGER)       AS date_key,
       ch.channel_id,
       m.spend_gbp
FROM fact_marketing m
JOIN tmp_channel ch ON ch.channel_code = m.channel
ORDER BY m.month, ch.channel_id;
