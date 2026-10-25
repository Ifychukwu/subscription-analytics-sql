"""Export the Harvest Box warehouse as Power BI-ready star-schema CSVs.

Writes to powerbi/:
  dim_date.csv, dim_customer.csv, dim_channel.csv, dim_plan.csv, dim_recipe.csv,
  fact_orders.csv, fact_order_items.csv, fact_cancellations.csv,
  fact_marketing_spend.csv, fact_web_sessions.csv, data_dictionary.md

Conventions: one CSV per table, UTF-8, comma-separated, header row, no index column,
ISO 8601 dates (YYYY-MM-DD), integer surrogate keys, date_key = YYYYMMDD integer.
The fact queries live in sql/powerbi/*.sql; the date dimension is generated here.

Usage:  python -m harvest.export_powerbi        (builds data/harvest.db first if missing)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from harvest.build_db import CHANNELS, DB, build
from harvest.run import SQL_DIR, connect, run_file

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "powerbi"
PBI_SQL = SQL_DIR / "powerbi"
DATE_START, DATE_END = "2024-01-01", "2026-12-31"   # whole calendar years covering every fact date

CHANNEL_NAMES = {"paid_social": "Paid social", "search": "Search", "referral": "Referral",
                 "tv": "TV", "affiliate_voucher": "Affiliate voucher"}

# Relationships: (from table, from column, to table, to column, active in Power BI).
# All are many-to-one with single cross-filter direction (the dimension filters the fact).
# The two inactive ones would create ambiguous filter paths; they are listed so the test
# still checks those keys, and the DAX measures in powerbi/README.md don't need them.
RELATIONSHIPS = [
    ("fact_orders", "date_key", "dim_date", "date_key", True),
    ("fact_orders", "customer_id", "dim_customer", "customer_id", True),
    ("fact_orders", "plan_id", "dim_plan", "plan_id", True),
    ("fact_order_items", "date_key", "dim_date", "date_key", True),
    ("fact_order_items", "customer_id", "dim_customer", "customer_id", True),
    ("fact_order_items", "recipe_id", "dim_recipe", "recipe_id", True),
    ("fact_cancellations", "date_key", "dim_date", "date_key", True),
    ("fact_cancellations", "customer_id", "dim_customer", "customer_id", True),
    ("fact_marketing_spend", "date_key", "dim_date", "date_key", True),
    ("fact_marketing_spend", "channel_id", "dim_channel", "channel_id", True),
    ("fact_web_sessions", "date_key", "dim_date", "date_key", True),
    ("dim_customer", "channel_id", "dim_channel", "channel_id", True),
    ("dim_customer", "signup_date_key", "dim_date", "date_key", False),
    ("dim_customer", "signup_plan_id", "dim_plan", "plan_id", False),
]

PRIMARY_KEYS = {
    "dim_date": ["date_key"], "dim_customer": ["customer_id"], "dim_channel": ["channel_id"],
    "dim_plan": ["plan_id"], "dim_recipe": ["recipe_id"], "fact_orders": ["order_id"],
    "fact_order_items": ["order_id", "recipe_id"], "fact_cancellations": ["customer_id"],
    "fact_marketing_spend": ["date_key", "channel_id"], "fact_web_sessions": ["session_id"],
}

DESCRIPTIONS = {
    "dim_date": {
        "date_key": "Surrogate key, YYYYMMDD integer", "date": "Calendar date (ISO)", "year": "Calendar year",
        "quarter": "Calendar quarter label, e.g. Q1", "quarter_number": "Calendar quarter 1-4",
        "month_number": "Month 1-12 (sort column for month_name)", "month_name": "Month name, e.g. January",
        "month_short": "Month abbreviation, e.g. Jan", "year_month": "YYYY-MM label",
        "month_start_date": "First day of the month (ISO)", "iso_year": "ISO 8601 week-numbering year",
        "iso_week": "ISO 8601 week number", "week_start_date": "Monday of the week (ISO); boxes are delivered weekly",
        "day_of_month": "Day 1-31", "day_of_week_number": "1 = Monday ... 7 = Sunday",
        "day_name": "Day name, e.g. Monday", "is_weekend": "1 if Saturday or Sunday",
        "season": "UK meteorological season (Winter = Dec-Feb)",
        "uk_fiscal_year": "UK financial year starting 1 April, e.g. FY2024/25",
    },
    "dim_customer": {
        "customer_id": "Customer key", "signup_date": "Sign-up date (ISO)",
        "signup_date_key": "Sign-up date as YYYYMMDD (inactive relationship to dim_date)",
        "region": "UK region", "channel_id": "Acquisition channel key", "signup_plan_id": "Plan chosen at sign-up",
        "age_band": "Self-reported age band", "first_box_date": "Date of first delivered box (blank if none)",
        "cohort_month": "First day of the month of the first delivered box (retention cohort)",
        "cancel_date": "Cancellation date (blank if still subscribed)", "has_cancelled": "1 if the customer has cancelled",
        "rfm_segment": "RFM segment, same rules as sql/07_rfm_segmentation.sql",
    },
    "dim_channel": {
        "channel_id": "Channel key", "channel_code": "Code used in the source database",
        "channel_name": "Display name",
    },
    "dim_plan": {
        "plan_id": "Plan key", "plan_name": "Plan name", "people": "People per box",
        "recipes_per_box": "Recipes per box", "weekly_price_gbp": "List price per box (GBP)",
    },
    "dim_recipe": {
        "recipe_id": "Recipe key", "recipe_name": "Recipe name", "cuisine": "Cuisine",
        "ingredient_cost_gbp": "Ingredient cost per person (GBP)", "cook_minutes": "Cooking time in minutes",
    },
    "fact_orders": {
        "order_id": "Box key (unique)", "customer_id": "Customer key", "delivery_date": "Delivery date (ISO)",
        "date_key": "Delivery date as YYYYMMDD", "plan_id": "Plan key", "status": "delivered or refunded",
        "is_delivered": "1 if delivered (revenue counts), 0 if refunded", "revenue_gbp": "Amount charged after discount (GBP)",
        "discount_gbp": "Discount given (GBP)", "ingredient_cost_gbp": "Ingredient cost of the box (GBP)",
        "fulfilment_cost_gbp": "Packaging and delivery cost, fixed at 6.50 (GBP)",
        "gross_margin_gbp": "revenue - ingredients - fulfilment (GBP)",
        "months_since_first_box": "Calendar months since the customer's first delivered box (0 = cohort month; -1 for a few refunded boxes before it)",
    },
    "fact_order_items": {
        "order_id": "Box key (degenerate dimension)", "recipe_id": "Recipe key", "customer_id": "Customer key",
        "date_key": "Delivery date as YYYYMMDD", "is_delivered": "1 if the box was delivered",
        "ingredient_cost_gbp": "Ingredient cost of this recipe for the box's number of people (GBP)",
    },
    "fact_cancellations": {
        "customer_id": "Customer key (one cancellation per customer)", "cancel_date": "Cancellation date (ISO)",
        "date_key": "Cancellation date as YYYYMMDD", "reason": "Reason given at cancellation",
        "boxes_received": "Delivered boxes before cancelling", "tenure_group": "Tenure bucket used in Q8",
    },
    "fact_marketing_spend": {
        "month_start_date": "First day of the month (ISO)", "date_key": "month_start_date as YYYYMMDD",
        "channel_id": "Channel key", "spend_gbp": "Marketing spend in the month (GBP)",
    },
    "fact_web_sessions": {
        "session_id": "Web session key", "visitor_id": "Pseudonymous visitor ID",
        "session_start": "Timestamp of the first event (ISO, local time)", "date_key": "Session start date as YYYYMMDD",
        "device": "mobile, desktop or tablet", "ab_variant": "Checkout A/B test arm (A = old, B = one-page checkout)",
        "reached_landing": "1 if the session reached the landing page", "reached_menu": "1 if it reached the menu",
        "reached_plan_select": "1 if it reached plan selection", "reached_checkout": "1 if it reached checkout",
        "purchased": "1 if it purchased",
    },
}


def dim_date(start: str = DATE_START, end: str = DATE_END) -> pd.DataFrame:
    d = pd.date_range(start, end, freq="D")
    iso = d.isocalendar()
    fy_start = d.year - (d.month < 4)
    season = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
              6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}
    return pd.DataFrame({
        "date_key": d.strftime("%Y%m%d").astype(int),
        "date": d.strftime("%Y-%m-%d"),
        "year": d.year,
        "quarter": "Q" + d.quarter.astype(str),
        "quarter_number": d.quarter,
        "month_number": d.month,
        "month_name": d.strftime("%B"),
        "month_short": d.strftime("%b"),
        "year_month": d.strftime("%Y-%m"),
        "month_start_date": d.to_period("M").start_time.strftime("%Y-%m-%d"),
        "iso_year": iso["year"].to_numpy(),
        "iso_week": iso["week"].to_numpy(),
        "week_start_date": (d - pd.to_timedelta(d.dayofweek, "D")).strftime("%Y-%m-%d"),
        "day_of_month": d.day,
        "day_of_week_number": d.dayofweek + 1,
        "day_name": d.strftime("%A"),
        "is_weekend": (d.dayofweek >= 5).astype(int),
        "season": d.month.map(season),
        "uk_fiscal_year": [f"FY{y}/{str(y + 1)[-2:]}" for y in fy_start],
    })


def dim_channel() -> pd.DataFrame:
    codes = list(CHANNELS)
    return pd.DataFrame({"channel_id": range(1, len(codes) + 1), "channel_code": codes,
                         "channel_name": [CHANNEL_NAMES[c] for c in codes]})


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    """Whole-number float columns (from SQL NULLs) become nullable integers, so CSVs show 3 not 3.0."""
    for col in df.columns:
        s = df[col]
        if s.dtype.kind == "f" and not col.endswith("_gbp") and s.dropna().mod(1).eq(0).all():
            df[col] = s.astype("Int64")
    return df


def build_tables(con: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    run_file(con, SQL_DIR / "02_clean_orders_view.sql")          # (re)creates v_orders
    channels = dim_channel()
    con.execute("DROP TABLE IF EXISTS temp.tmp_channel")
    con.execute("CREATE TEMP TABLE tmp_channel (channel_id INTEGER, channel_code TEXT)")
    con.executemany("INSERT INTO tmp_channel VALUES (?, ?)", channels[["channel_id", "channel_code"]].values.tolist())

    tables = {
        "dim_date": dim_date(),
        "dim_channel": channels,
        "dim_plan": pd.read_sql("SELECT * FROM dim_plans ORDER BY plan_id", con),
        "dim_recipe": pd.read_sql("SELECT * FROM dim_recipes ORDER BY recipe_id", con),
    }
    for name in ("dim_customer", "fact_orders", "fact_order_items", "fact_cancellations",
                 "fact_marketing_spend", "fact_web_sessions"):
        tables[name] = run_file(con, PBI_SQL / f"{name}.sql")
    return {k: _tidy(v) for k, v in tables.items()}


def data_dictionary(tables: dict[str, pd.DataFrame]) -> str:
    kind = {"i": "Whole number", "u": "Whole number", "f": "Decimal number", "O": "Text", "b": "Whole number"}
    lines = ["# Data dictionary (generated by `python -m harvest.export_powerbi`)", ""]
    for name, df in tables.items():
        pk = ", ".join(PRIMARY_KEYS[name])
        lines += [f"## {name}.csv", "", f"{len(df):,} rows · primary key: `{pk}`", "",
                  "| Column | Power BI type | Description |", "|---|---|---|"]
        for col in df.columns:
            t = "Whole number" if str(df[col].dtype) == "Int64" else kind.get(df[col].dtype.kind, "Text")
            if col.endswith("_date") or col == "date" or col == "cohort_month":
                t = "Date"
            elif col == "session_start":
                t = "Date/Time"
            elif col.endswith("_gbp"):
                t = "Fixed decimal (currency)"
            lines.append(f"| `{col}` | {t} | {DESCRIPTIONS[name][col]} |")
        lines.append("")
    return "\n".join(lines)


def export(db: str | Path = DB, out: str | Path = OUT) -> dict[str, pd.DataFrame]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    con = connect(db)
    try:
        tables = build_tables(con)
    finally:
        con.close()
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8", lineterminator="\n")
    (out / "data_dictionary.md").write_text(data_dictionary(tables), encoding="utf-8")
    return tables


def main() -> None:
    if not DB.exists():
        build()
    tables = export()
    for name, df in tables.items():
        size = (OUT / f"{name}.csv").stat().st_size / 1e6
        print(f"{name:22s} {len(df):>8,} rows  {size:6.2f} MB")


if __name__ == "__main__":
    main()
