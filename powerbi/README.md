# Power BI: Harvest Box star schema

This folder holds a **Power BI-ready export** of the Harvest Box warehouse: clean CSVs in a star schema, plus everything needed to rebuild the case study as a three-page dashboard. Column-level documentation is in [data_dictionary.md](data_dictionary.md).

Regenerate the files at any time:

```bash
PYTHONPATH=src python -m harvest.export_powerbi   # reads data/harvest.db (builds it if missing), ~10 s
```

The fact queries are plain SQL in [`sql/powerbi/`](../sql/powerbi); the date dimension is generated in Python (`src/harvest/export_powerbi.py`). `tests/test_powerbi_export.py` checks that row counts match the database, every primary key is unique, there are no orphan foreign keys, the date table is contiguous, and that LTV:CAC computed from the CSVs reproduces the SQL answer (Q6).

## The files

| File | Grain | Rows | Notes |
|---|---|---|---|
| `dim_date.csv` | one row per day, 2024-01-01 to 2026-12-31 | 1,096 | `date_key` = YYYYMMDD; month, ISO week, season, UK fiscal year |
| `dim_customer.csv` | customer | 12,000 | region, age band, channel, cohort month, cancellation flag, RFM segment |
| `dim_channel.csv` | acquisition channel | 5 | shared by customers and marketing spend |
| `dim_plan.csv` | subscription plan | 4 | |
| `dim_recipe.csv` | recipe | 60 | |
| `fact_orders.csv` | box (`order_id`) | 124,409 | delivered **and** refunded boxes; revenue, costs, gross margin, months since first box |
| `fact_order_items.csv` | recipe in a box | 423,620 | carries `date_key`, `customer_id`, `is_delivered` so it joins straight to the dimensions |
| `fact_cancellations.csv` | cancellation | 10,422 | reason, boxes received, tenure group |
| `fact_marketing_spend.csv` | channel × month | 150 | `date_key` is the first day of the month |
| `fact_web_sessions.csv` | web session | 26,000 | device, A/B variant, 0/1 flag per funnel step |

**Cleaning applied** (same rules as `sql/02_clean_orders_view.sql`): the 15 duplicate order rows are removed, the 5 orders for unknown customers are dropped, and the 8 orders with missing revenue are excluded. Refunded boxes are **kept** with `status = "refunded"` and `is_delivered = 0`, so the refund rate can be reported; every revenue measure below filters to `is_delivered = 1`, which reproduces the SQL case study exactly (121,369 delivered boxes, £6,475,594 revenue).

Format: UTF-8, comma-separated, header row, no index column, ISO 8601 dates (`YYYY-MM-DD`), timestamps as `YYYY-MM-DD HH:MM:SS`. The largest file is 12.8 MB.

## 1. Load the data in Power BI Desktop

**Option A: Text/CSV (simplest).** *Home → Get Data → Text/CSV*, pick a file, check that *File origin* is **65001: Unicode (UTF-8)** and *Delimiter* is **Comma**, then **Transform Data**. Repeat for all ten CSVs. Keep the query names as the file names (`fact_orders`, `dim_date`…), because the DAX below uses them.

**Option B: Folder, with a re-pointable path.** Useful if you move the folder or refresh from a new export.
1. *Home → Transform data → Manage Parameters → New*: name `PbiFolder`, type Text, value e.g. `C:\repos\subscription-analytics-sql\powerbi\` (with the trailing backslash).
2. *Home → New Source → Blank Query → Advanced Editor*, paste and rename the query to `fact_orders`:
   ```powerquery
   let
       Source   = Csv.Document(File.Contents(PbiFolder & "fact_orders.csv"),
                      [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
       Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
   in
       Promoted
   ```
3. Duplicate the query for the other nine files, changing the file name. (*Get Data → Folder* also works, but its default *Combine* would stack all files into one table; use *Transform Data* and drill into each file's **Binary** instead.)

**Data types** (Power Query usually detects them; check these):
- `*_key`, `*_id`, flags (`is_delivered`, `has_cancelled`, `reached_*`, `purchased`) and counts: **Whole number**
- `date`, `*_date`, `cohort_month`: **Date**. `session_start`: **Date/Time**
- `*_gbp`: **Fixed decimal number** (currency)

Then *Close & Apply*.

**Model settings**
- Select `dim_date` → *Table tools → Mark as date table* → column `date`. This is required for the time-intelligence measures because the relationships use the integer `date_key`.
- Sort `dim_date[month_name]` and `[month_short]` by `month_number`, and `dim_date[day_name]` by `day_of_week_number` (*Column tools → Sort by column*).
- Hide all `*_key` and `*_id` columns on the fact tables from report view.
- Create an empty table for measures: *Home → Enter data*, name it `_Measures`.

## 2. Relationships

Create these in *Model view* (Power BI may auto-detect some; delete any it guesses wrongly). All are **many-to-one (\*:1)** with **single** cross-filter direction, so filters flow from dimensions to facts.

| From (many side) | To (one side) | Cardinality | Cross-filter | Active |
|---|---|---|---|---|
| `fact_orders[date_key]` | `dim_date[date_key]` | \*:1 | Single | Yes |
| `fact_orders[customer_id]` | `dim_customer[customer_id]` | \*:1 | Single | Yes |
| `fact_orders[plan_id]` | `dim_plan[plan_id]` | \*:1 | Single | Yes |
| `fact_order_items[date_key]` | `dim_date[date_key]` | \*:1 | Single | Yes |
| `fact_order_items[customer_id]` | `dim_customer[customer_id]` | \*:1 | Single | Yes |
| `fact_order_items[recipe_id]` | `dim_recipe[recipe_id]` | \*:1 | Single | Yes |
| `fact_cancellations[date_key]` | `dim_date[date_key]` | \*:1 | Single | Yes |
| `fact_cancellations[customer_id]` | `dim_customer[customer_id]` | \*:1 | Single | Yes |
| `fact_marketing_spend[date_key]` | `dim_date[date_key]` | \*:1 | Single | Yes |
| `fact_marketing_spend[channel_id]` | `dim_channel[channel_id]` | \*:1 | Single | Yes |
| `fact_web_sessions[date_key]` | `dim_date[date_key]` | \*:1 | Single | Yes |
| `dim_customer[channel_id]` | `dim_channel[channel_id]` | \*:1 | Single | Yes |
| `dim_customer[signup_date_key]` | `dim_date[date_key]` | \*:1 | Single | **No** (optional) |
| `dim_customer[signup_plan_id]` | `dim_plan[plan_id]` | \*:1 | Single | **No** (optional) |

Notes:
- `dim_channel` filters both customers (and through them their orders) and marketing spend, which is what makes LTV:CAC by channel work.
- The last two would create a second filter path from `dim_date` / `dim_plan` to `fact_orders`, so they must stay inactive. The measures below don't need them; sign-ups by date are counted by key range instead.
- `fact_web_sessions` has no customer key: web visitors are not linked to customers in the source data.
- `order_id` in `fact_order_items` is a degenerate dimension; there is deliberately no fact-to-fact relationship.

## 3. DAX measures

Create each in `_Measures` (*New measure*). Set format strings as noted.

### Revenue and margin

```dax
Revenue =
CALCULATE ( SUM ( fact_orders[revenue_gbp] ), fact_orders[is_delivered] = 1 )

Boxes Delivered =
CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_delivered] = 1 )

Average Box Value =
DIVIDE ( [Revenue], [Boxes Delivered] )

Active Customers =
CALCULATE ( DISTINCTCOUNT ( fact_orders[customer_id] ), fact_orders[is_delivered] = 1 )

Gross Margin =
CALCULATE ( SUM ( fact_orders[gross_margin_gbp] ), fact_orders[is_delivered] = 1 )

Gross Margin % =
DIVIDE ( [Gross Margin], [Revenue] )

Refund Rate =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[status] = "refunded" ),
    COUNTROWS ( fact_orders )
)

Revenue Previous Month =
CALCULATE ( [Revenue], DATEADD ( dim_date[date], -1, MONTH ) )

Revenue MoM % =
DIVIDE ( [Revenue] - [Revenue Previous Month], [Revenue Previous Month] )

Revenue YoY % =
VAR PriorYear = CALCULATE ( [Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )
RETURN
    DIVIDE ( [Revenue] - PriorYear, PriorYear )
```
Formats: currency £ for money, percentage for `%` measures.

### Customers, acquisition and LTV:CAC

```dax
Customers =
COUNTROWS ( dim_customer )

New Customers =
-- sign-ups in the selected dates, without an active customer-to-date relationship
VAR FirstKey = MIN ( dim_date[date_key] )
VAR LastKey  = MAX ( dim_date[date_key] )
RETURN
    CALCULATE (
        COUNTROWS ( dim_customer ),
        dim_customer[signup_date_key] >= FirstKey,
        dim_customer[signup_date_key] <= LastKey
    )

Marketing Spend =
SUM ( fact_marketing_spend[spend_gbp] )

CAC =
DIVIDE ( [Marketing Spend], [New Customers] )

LTV to CAC =
-- lifetime gross margin of a channel's customers ÷ that channel's total spend (same as sql/06)
CALCULATE ( DIVIDE ( [Gross Margin], [Marketing Spend] ), REMOVEFILTERS ( dim_date ) )
```

### Retention (cohorts)

```dax
Cohort Size =
CALCULATE (
    [Active Customers],
    REMOVEFILTERS ( fact_orders[months_since_first_box] ),
    fact_orders[months_since_first_box] = 0
)

Retention % =
DIVIDE ( [Active Customers], [Cohort Size] )
```
Use in a matrix with rows `dim_customer[cohort_month]` and columns `fact_orders[months_since_first_box]` (visual filter 0 to 12). Don't put a date slicer on this visual: it would cut cohorts short.

### Segments and cancellations

```dax
Customer Share % =
DIVIDE ( [Customers], CALCULATE ( [Customers], REMOVEFILTERS ( dim_customer[rfm_segment] ) ) )

Revenue Share % =
DIVIDE ( [Revenue], CALCULATE ( [Revenue], REMOVEFILTERS ( dim_customer[rfm_segment] ) ) )

Cancellations =
COUNTROWS ( fact_cancellations )

Cancellation Reason Share % =
DIVIDE (
    [Cancellations],
    CALCULATE ( [Cancellations], REMOVEFILTERS ( fact_cancellations[reason] ) )
)
```
For segment shares that match `results/07_rfm_segmentation.csv`, add a visual-level filter excluding `rfm_segment = "No delivered boxes"` (377 customers who signed up but never received a delivered box).

### Recipes (Pareto)

```dax
Recipe Lines =
CALCULATE ( COUNTROWS ( fact_order_items ), fact_order_items[is_delivered] = 1 )

Recipe Share % =
DIVIDE ( [Recipe Lines], CALCULATE ( [Recipe Lines], REMOVEFILTERS ( dim_recipe ) ) )

Recipe Rank =
RANKX ( ALLSELECTED ( dim_recipe ), [Recipe Lines] )

Cumulative Recipe Share % =
VAR CurrentLines = [Recipe Lines]
VAR Recipes =
    ADDCOLUMNS ( ALLSELECTED ( dim_recipe ), "@lines", [Recipe Lines] )
RETURN
    DIVIDE (
        SUMX ( FILTER ( Recipes, [@lines] >= CurrentLines ), [@lines] ),
        SUMX ( Recipes, [@lines] )
    )
```

### Funnel and A/B test

```dax
Sessions =
COUNTROWS ( fact_web_sessions )

Reached Menu =
SUM ( fact_web_sessions[reached_menu] )

Reached Plan Select =
SUM ( fact_web_sessions[reached_plan_select] )

Checkout Sessions =
SUM ( fact_web_sessions[reached_checkout] )

Purchases =
SUM ( fact_web_sessions[purchased] )

Conversion % =
DIVIDE ( [Purchases], [Sessions] )

Checkout to Purchase % =
DIVIDE (
    CALCULATE ( [Purchases], fact_web_sessions[reached_checkout] = 1 ),
    [Checkout Sessions]
)

Checkout Conversion A =
CALCULATE ( [Checkout to Purchase %], fact_web_sessions[ab_variant] = "A" )

Checkout Conversion B =
CALCULATE ( [Checkout to Purchase %], fact_web_sessions[ab_variant] = "B" )

AB Relative Lift % =
DIVIDE ( [Checkout Conversion B] - [Checkout Conversion A], [Checkout Conversion A] )

AB z-score =
-- two-proportion z-test on checkout → purchase, as in sql/11_ab_test_checkout.sql
VAR nA = CALCULATE ( [Checkout Sessions], fact_web_sessions[ab_variant] = "A" )
VAR nB = CALCULATE ( [Checkout Sessions], fact_web_sessions[ab_variant] = "B" )
VAR xA = CALCULATE ( [Purchases], fact_web_sessions[ab_variant] = "A", fact_web_sessions[reached_checkout] = 1 )
VAR xB = CALCULATE ( [Purchases], fact_web_sessions[ab_variant] = "B", fact_web_sessions[reached_checkout] = 1 )
VAR pA = DIVIDE ( xA, nA )
VAR pB = DIVIDE ( xB, nB )
VAR pPooled = DIVIDE ( xA + xB, nA + nB )
VAR StdErr = SQRT ( pPooled * ( 1 - pPooled ) * ( 1 / nA + 1 / nB ) )
RETURN
    DIVIDE ( pB - pA, StdErr )

AB Verdict =
IF ( ABS ( [AB z-score] ) > 1.96, "Significant at 5%", "Not significant" )
```

**Expected values** (whole period, no slicers), useful to check the model: Revenue £6,475,594 · Boxes Delivered 121,369 · Gross Margin % 21.7% · LTV to CAC Referral 11.74, Search 3.11, Paid social 2.25, Affiliate voucher 1.75, TV 1.67 · Checkout Conversion A 56.5%, B 61.4%, lift 8.7%, z 3.53 · Conversion % mobile 9.2%, desktop 15.3%.

## 4. Suggested dashboard (3 pages)

### Page 1: Executive overview, "Growing, seasonal, but leaky"
- **KPI cards** (top row): Revenue, Boxes Delivered, Active Customers, Average Box Value, Gross Margin %, Refund Rate.
- **Line chart**: Revenue by `dim_date[year_month]`, with Revenue MoM % in the tooltip. Shows growth of roughly 6× through 2024 and the winter peak / summer dip (Q3, Q14).
- **Clustered bar**: Revenue by `dim_customer[region]`, with `dim_date[season]` as legend (Q14).
- **Slicers**: `dim_date[year]`, `dim_customer[region]`, `dim_channel[channel_name]`.
- **Text box**: data-quality note: 15 duplicates, 8 missing revenue and 5 orphan orders removed (Q1).

### Page 2: Customers and channels, "Retention is the biggest lever"
- **Matrix heat-map**: Retention % by `cohort_month` × `months_since_first_box` (0–12), background colour scale. About 40% of a cohort still orders in month 3 and about 20% in month 6 (Q4).
- **Bar chart**: LTV to CAC by `dim_channel[channel_name]`, with a constant line at 3 (*Analytics pane → Constant line*). Referral 11.7; TV and affiliate vouchers below 3:1 (Q6).
- **Clustered bar**: Customer Share % and Revenue Share % by `rfm_segment` (filter out "No delivered boxes"). Champions: 18% of customers, 39% of revenue (Q7).
- **100% stacked bar**: Cancellations by `fact_cancellations[tenure_group]`, legend `reason`. Price (~31%) and lack of time (~20%) lead at every tenure (Q8).
- **Slicer**: `dim_channel[channel_name]` (filters the cohort matrix by channel, Q5).

### Page 3: Product and conversion, "Few recipes, mobile leaks, checkout B wins"
- **Line and clustered column chart**: Recipe Lines (columns) and Cumulative Recipe Share % (line, secondary axis) by `dim_recipe[recipe_name]`, sorted by Recipe Lines descending. Top 10 of 60 recipes = 50% of demand (Q9).
- **Funnel visual** (or clustered bar): Sessions, Reached Menu, Reached Plan Select, Checkout Sessions, Purchases, with a `device` slicer; plus a table of Conversion % by device. Mobile 9.2% vs desktop 15.3% (Q10).
- **A/B cards**: Checkout Conversion A, Checkout Conversion B, AB Relative Lift %, AB z-score, AB Verdict. B lifts checkout → purchase from 56.5% to 61.4% (+8.7%, z = 3.53) (Q11).

## Caveats
- The data is **synthetic** (see [data/README.md](../data/README.md)); the dashboard demonstrates method, not a real business.
- `rfm_segment` uses `NTILE` quintiles, which split tied values arbitrarily. The export mirrors Q7's query so segments match its results exactly, but a different SQL engine could place a few tied customers differently.
- `age_band` is included as a descriptive attribute. Use it to check that retention or offers don't differ unfairly by age, not to target individuals.
