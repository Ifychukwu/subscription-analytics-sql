# models/

This is a **SQL analytics project**, so there are no trained machine-learning models and this folder is intentionally empty.

The "logic" of the project lives elsewhere:

| What | Where |
|---|---|
| Business rules and analyses (cleaning, cohorts, LTV:CAC, RFM segments, funnel, A/B test) | [`sql/`](../sql), one file per question |
| Power BI star-schema export queries | [`sql/powerbi/`](../sql/powerbi) and `src/harvest/export_powerbi.py` |
| Rule-based customer segments (RFM) | `sql/07_rfm_segmentation.sql`; exported per customer as `dim_customer.rfm_segment` |
| Query outputs | [`results/`](../results) |
| Dashboard-ready data | [`powerbi/`](../powerbi) |

The folder exists to keep the same layout as the other projects in this portfolio. A natural next step that *would* put a model here is a churn-propensity classifier trained on the order history (for example, predicting cancellation in the next 4 weeks from recency, frequency, discount use and tenure).
