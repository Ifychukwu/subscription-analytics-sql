# Methods

## 1. Warehouse
SQLite star schema built by `src/harvest/build_db.py` (dimensions `dim_customers`, `dim_plans`, `dim_recipes`; facts `fact_orders`, `fact_order_items`, `fact_cancellations`, `fact_events`, `fact_marketing`). See [data/README.md](../data/README.md) for the generator and planted patterns.

## 2. Workflow
1. **Check before analysing** (Q1). Six checks run as one `UNION ALL` query: duplicates via `GROUP BY … HAVING COUNT(*) > 1`, nulls, and anti-joins (`LEFT JOIN … WHERE key IS NULL`) for orphans and impossible dates.
2. **One source of truth** (Q2). The view `v_orders` removes duplicates with `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY rowid)`, drops orphan customers by inner join, and keeps delivered rows with revenue. Every later query reads `v_orders`, so a cleaning rule changes in one place.
3. **One question per file.** Each `sql/NN_*.sql` opens with the business question and the techniques used, and ends with exactly one `SELECT`. `src/harvest/run.py` splits statements with `sqlite3.complete_statement` (safe for `;` inside strings), runs them, saves `results/NN_*.csv` and draws the charts.

## 3. Analyses

| # | Method |
|---|---|
| 03 | Monthly revenue with `strftime('%Y-%m')`; MoM and YoY growth with `LAG(…, 1)` and `LAG(…, 12)`; `NULLIF` guards division by zero |
| 04 | Cohort = month of first delivered box; month offset = 12·Δyear + Δmonth; retention = active customers ÷ `FIRST_VALUE(customers)` in the cohort |
| 05 | Months since first box as days ÷ 30.44; active in month 3 means any box in [3, 4); `AVG(…) FILTER (WHERE first_date <= cut-off)` counts only cohorts old enough to observe |
| 06 | Facts at different grains are aggregated separately (box cost per order, margin per customer, spend per channel, sign-ups per channel) before joining, to avoid fan-out. LTV = gross margin per acquired customer; CAC = spend ÷ sign-ups |
| 07 | RFM: `NTILE(5)` on recency (as of 2026-06-29), frequency and monetary value; rule-based segments from R and F scores; `SUM(COUNT(*)) OVER ()` for shares |
| 08 | Tenure = delivered boxes before the cancellation date (`LEFT JOIN` with a date condition); share within group with `SUM() OVER (PARTITION BY tenure_group)` |
| 09 | Pareto: running total `SUM() OVER (ORDER BY times_ordered DESC ROWS UNBOUNDED PRECEDING)` |
| 10 | Pivot events to one row per session with `MAX(event_name = 'step')`, then step-to-step conversion |
| 11 | Two-proportion z-test on checkout → purchase: pooled p = (x_A + x_B)/(n_A + n_B); z = (p_B − p_A)/√(p(1−p)(1/n_A + 1/n_B)); significant if \|z\| > 1.96 |
| 12 | Gaps and islands: `LAG` gives minutes since the visitor's previous event; a gap > 30 min starts a session; a running `SUM` of start flags numbers sessions |
| 13 | Percentiles without a percentile function: `CUME_DIST()` and the first value at or past each cut-off |
| 14 | Seasonal index = a region's average weekly boxes in a month ÷ its own 2025 average (`AVG() OVER (PARTITION BY region)`) |
| 15 | `EXPLAIN QUERY PLAN` and timing (20 runs) before and after a covering index on `(customer_id, delivery_date, revenue_gbp)` |

`run.connect()` registers `sqrt`, `ln` and `power` as Python functions if the SQLite build lacks the math extension.

## 4. Testing
`tests/test_sql.py` builds a smaller warehouse (1,500 customers, different seed) and checks each answer against an independent pandas calculation (cleaning, monthly revenue, funnel, z-score) or an invariant (cohort month 0 = 100%, shares sum to 100%, running totals are monotonic, the index changes the plan). Using a different seed shows the SQL is correct in general, not tuned to one dataset.

## 5. Power BI export (`src/harvest/export_powerbi.py`, `sql/powerbi/`)
- **Star schema.** Five dimensions (`dim_date`, `dim_customer`, `dim_channel`, `dim_plan`, `dim_recipe`) and five facts (`fact_orders`, `fact_order_items`, `fact_cancellations`, `fact_marketing_spend`, `fact_web_sessions`). `dim_channel` is a conformed dimension shared by customers and marketing spend, which makes LTV:CAC by channel a simple ratio of two measures.
- **Keys.** Integer natural keys from the source (`customer_id`, `plan_id`, `recipe_id`, `order_id`, `session_id`), a new integer `channel_id`, and `date_key` = YYYYMMDD. Marketing spend (monthly grain) links to the first day of the month.
- **Date dimension.** Generated in pandas for whole calendar years 2024–2026 (1,096 days): month, quarter, ISO week, Monday week start, UK meteorological season and UK fiscal year (April–March).
- **Pre-computed business logic.** Columns that are awkward in DAX are computed once in SQL: gross margin per box (same cost rules as Q6), `months_since_first_box` (Q4 definition), `cohort_month`, `rfm_segment` (Q7 rules, same window order so `NTILE` ties break identically), tenure group (Q8), and funnel step flags per session (Q10).
- **Refunds kept.** Unlike `v_orders`, `fact_orders` keeps refunded boxes with `is_delivered = 0`, so refund rate is available; revenue measures filter on `is_delivered = 1`.
- **Format.** UTF-8 CSV, no index column, ISO dates, nullable integers written without `.0`.
- **Tests** (`tests/test_powerbi_export.py`): row counts against the database (including an independent pandas cleaning of orders), unique primary keys, no orphan foreign keys for every relationship, contiguous date table, documented columns, ISO dates, file size under 25 MB, and LTV:CAC from the CSVs equal to Q6.
