# System card: Harvest Box SQL analytics and Power BI export

| | |
|---|---|
| **System** | 15 SQL analyses over a SQLite star schema, a Python runner, and a Power BI star-schema export |
| **Type** | Descriptive analytics and one statistical test (two-proportion z-test). No machine-learning model. |
| **Data** | Synthetic warehouse for a fictional UK meal-kit subscription company: 12,000 customers, 121,369 clean deliveries, 423,648 recipe lines, 26,000 web sessions, 30 months (see [data/README.md](../data/README.md)) |
| **Outputs** | `results/*.csv` (one per question), `reports/figures/*.png`, `powerbi/*.csv` + `powerbi/README.md` |
| **Checks** | 22 tests: every SQL answer is cross-checked against an independent pandas calculation; the Power BI export is checked for row counts, unique keys and orphan foreign keys |

## Intended use
A portfolio case study showing how an analyst answers leadership questions with readable SQL: data-quality checks first, a single cleaned view, then growth, retention, unit economics, segmentation, funnel and experiment analysis, handed over to BI as a documented star schema.

## Out of scope
- Decisions about real customers or real marketing budgets: the data is synthetic.
- Individual-level automated decisions (for example, withholding offers from a segment) without human review.
- Causal claims beyond the randomised A/B test (Q11). Channel and segment differences are associations.

## Results (all from `results/*.csv`, reproducible with `python -m harvest.run`)

| Question | Answer |
|---|---|
| Q1 Data quality | 15 duplicate orders, 8 with missing revenue, 5 for unknown customers; 0 for the other three checks |
| Q2 Clean view | 124,437 raw rows → 121,369 delivered, clean rows (3,043 refunded rows excluded) |
| Q3 Growth | Revenue £33,901 (Jan 2024) → £218,369 (Dec 2024), about 6.4× |
| Q4 Retention | e.g. Jan 2024 cohort: 44.5% active in month 3, 19.7% in month 6 |
| Q5 Retention by channel | Month 6: referral 31.3%, search 19.5%, TV 15.6%, paid social 13.0%, affiliate voucher 4.0% |
| Q6 LTV:CAC | Referral 11.74, search 3.11, paid social 2.25, affiliate voucher 1.75, TV 1.67 |
| Q7 RFM | Champions: 18.2% of customers, 38.7% of revenue; At risk: 11.8% / 17.7% |
| Q8 Cancellations | "Too expensive" ~31% and "not enough time to cook" ~20% in every tenure group |
| Q9 Recipes | Top 10 of 60 recipes = 50% of recipe lines |
| Q10 Funnel | Overall conversion: mobile 9.17%, desktop 15.31%, tablet 10.81% |
| Q11 A/B test | Checkout → purchase: A 56.46% (n = 2,455), B 61.39% (n = 2,484); +8.7% relative, z = 3.53, significant at 5% |
| Q12 Sessionization | 25,988 sessions rebuilt from raw events vs 26,000 logged (30-minute inactivity rule) |
| Q13 Spend | Median lifetime spend £350.93; 90th percentile £1,348.54 |
| Q14 Seasonality | e.g. London: seasonal index 1.08 in January, 0.80 in August (2025) |
| Q15 Indexing | Covering index turns a full SCAN into an index SEARCH; 5.5 ms → 0.65 ms on this machine (timings vary by hardware) |

## Limitations
- **Synthetic data.** Patterns were planted by the generator, so the analysis demonstrates method; the findings are not evidence about the meal-kit market.
- **LTV is realised, not predicted.** Lifetime value is gross margin to date, so recent cohorts look worse than they will be. A survival-based LTV would correct this.
- **Cost assumptions.** Gross margin uses ingredient costs plus a flat £6.50 packaging and delivery cost per box; real fulfilment costs vary by region and box size.
- **Retention definitions differ by question**: Q4 uses calendar-month offsets, Q5 uses 30.44-day months and only counts cohorts old enough to be measured. Both are documented in the SQL headers.
- **RFM uses NTILE quintiles**, which split tied values arbitrarily; a different engine could move a few tied customers between segments.
- **A/B test**: one fixed-horizon test at the 5% level. No correction for peeking or multiple metrics, and the test measures checkout → purchase only.
- **SQLite dialect.** Date functions (`strftime`, `julianday`) need small changes for PostgreSQL, BigQuery or Snowflake.

## Ethical considerations
- **Privacy (UK GDPR).** In a real deployment `dim_customers` and `fact_events` are personal data. The analysis needs only pseudonymous IDs; names, addresses and emails are not required and should stay out of the analytics warehouse. The Power BI export carries customer IDs and age band only, and web visitors are not linked to customers.
- **Fairness.** `age_band` and `region` are descriptive only. If segments drive offers, check that discounts and retention outreach don't systematically exclude groups (for example, older customers or Wales/Scotland), and keep humans in the loop for offer decisions.
- **Marketing decisions.** Low LTV:CAC for TV and vouchers is a reason to investigate, not an automatic budget cut: brand effects and attribution windows are not modelled.
