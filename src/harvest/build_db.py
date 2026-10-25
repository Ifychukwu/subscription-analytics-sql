"""Build the Harvest Box warehouse: a synthetic UK meal-kit subscription business.

Star-ish schema:
  dim_customers   one row per customer (signup date, region, acquisition channel)
  dim_plans       subscription plans
  dim_recipes     recipes (products) with cuisine and cost
  fact_orders     weekly box deliveries (status, revenue, discount)
  fact_order_items recipes in each box
  fact_events     raw web/app events (page views → checkout), includes an A/B test
  fact_marketing  monthly spend by channel (for CAC)
  fact_cancellations  cancellation date and reason

Planted patterns for the analysis to discover: cohort retention decay with
better retention for referral customers, a winter seasonal peak, a checkout
A/B test where variant B lifts conversion, Pareto-shaped recipe demand, and a
handful of deliberate data-quality problems.

Usage:  python -m harvest.build_db   (writes data/harvest.db)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path(__file__).resolve().parents[2] / "data" / "harvest.db"
REGIONS = ["London", "South East", "North West", "Midlands", "Scotland", "Yorkshire", "South West", "Wales"]
CHANNELS = {"paid_social": (0.34, 0.80), "search": (0.26, 0.95), "referral": (0.15, 1.35),
            "tv": (0.10, 0.90), "affiliate_voucher": (0.15, 0.55)}  # share, retention multiplier
PLANS = [(1, "2 people · 3 recipes", 2, 3, 41.99), (2, "2 people · 4 recipes", 2, 4, 51.99),
         (3, "4 people · 3 recipes", 4, 3, 64.99), (4, "4 people · 4 recipes", 4, 4, 79.99)]
CUISINES = {"British": 9, "Italian": 10, "Asian": 10, "Mexican": 6, "Indian": 8, "Mediterranean": 7, "Vegan": 6, "American": 4}


def build(path: str | Path = DB, n_customers: int = 12_000, seed: int = 17) -> Path:
    rng = np.random.default_rng(seed)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    start, end = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-06-28")
    weeks = pd.date_range(start, end, freq="W-MON")

    # --- customers -------------------------------------------------------------
    ch_names = list(CHANNELS)
    channel = rng.choice(ch_names, n_customers, p=[CHANNELS[c][0] for c in ch_names])
    # signups grow over time with a January "new year" spike
    signup_weights = np.linspace(1, 1.8, len(weeks)) * np.where(weeks.month == 1, 1.6, 1.0)
    signup_week = rng.choice(len(weeks), n_customers, p=signup_weights / signup_weights.sum())
    signup = weeks[signup_week] + pd.to_timedelta(rng.integers(0, 7, n_customers), "D")
    customers = pd.DataFrame({
        "customer_id": np.arange(1, n_customers + 1),
        "signup_date": signup.strftime("%Y-%m-%d"),
        "region": rng.choice(REGIONS, n_customers, p=[0.2, 0.16, 0.13, 0.14, 0.09, 0.1, 0.11, 0.07]),
        "acquisition_channel": channel,
        "plan_id": rng.choice([1, 2, 3, 4], n_customers, p=[0.38, 0.27, 0.22, 0.13]),
        "age_band": rng.choice(["18-24", "25-34", "35-44", "45-54", "55+"], n_customers, p=[0.08, 0.34, 0.3, 0.17, 0.11]),
    })

    # --- recipes --------------------------------------------------------------
    rec_rows, rid = [], 1
    for cuisine, k in CUISINES.items():
        for j in range(k):
            rec_rows.append((rid, f"{cuisine} recipe {j + 1}", cuisine, round(float(rng.uniform(2.2, 5.5)), 2),
                             int(rng.integers(20, 50))))
            rid += 1
    recipes = pd.DataFrame(rec_rows, columns=["recipe_id", "recipe_name", "cuisine", "ingredient_cost_gbp", "cook_minutes"])
    recipe_pop = rng.pareto(1.3, len(recipes)) + 0.2  # long-tailed demand

    # --- orders, cancellations ------------------------------------------------
    plan_price = {p[0]: p[4] for p in PLANS}
    plan_recipes = {p[0]: p[3] for p in PLANS}
    orders, items, cancels = [], [], []
    oid = 1
    reasons = ["too expensive", "moving to another provider", "not enough time to cook", "recipes repetitive",
               "delivery problems", "just trying it out"]
    for c in customers.itertuples():
        weekly_churn = 0.055 / CHANNELS[c.acquisition_channel][1]
        first = pd.Timestamp(c.signup_date) + pd.Timedelta(days=int(rng.integers(2, 8)))
        week = first
        n = 0
        while week <= end:
            # skip some weeks (pauses), more in summer
            skip_p = 0.18 + (0.12 if week.month in (7, 8) else 0) - (0.06 if week.month in (11, 12, 1) else 0)
            if rng.random() > skip_p:
                discount = 0.5 if n == 0 and c.acquisition_channel == "affiliate_voucher" else (0.25 if n == 0 else 0.0)
                status = rng.choice(["delivered", "refunded"], p=[0.975, 0.025])
                orders.append((oid, c.customer_id, week.strftime("%Y-%m-%d"), int(c.plan_id), status,
                               round(plan_price[c.plan_id] * (1 - discount), 2), round(plan_price[c.plan_id] * discount, 2)))
                chosen = rng.choice(len(recipes), plan_recipes[c.plan_id], replace=False, p=recipe_pop / recipe_pop.sum())
                items += [(oid, int(recipes.recipe_id.iloc[r])) for r in chosen]
                oid += 1
                n += 1
            if rng.random() < weekly_churn * (1.6 if n <= 2 else 1.0):
                cancels.append((c.customer_id, (week + pd.Timedelta(days=int(rng.integers(1, 6)))).strftime("%Y-%m-%d"),
                                rng.choice(reasons, p=[0.31, 0.14, 0.2, 0.15, 0.08, 0.12])))
                break
            week += pd.Timedelta(days=7)

    orders = pd.DataFrame(orders, columns=["order_id", "customer_id", "delivery_date", "plan_id", "status",
                                           "revenue_gbp", "discount_gbp"])
    items = pd.DataFrame(items, columns=["order_id", "recipe_id"])
    cancellations = pd.DataFrame(cancels, columns=["customer_id", "cancel_date", "reason"])

    # --- web events & A/B test (last 12 weeks) -----------------------------------
    ev, sid = [], 1
    test_start = pd.Timestamp("2026-04-06")
    for _ in range(26_000):
        day = test_start + pd.Timedelta(days=int(rng.integers(0, 84)))
        ts = day + pd.Timedelta(seconds=int(rng.integers(0, 86400)))
        device = rng.choice(["mobile", "desktop", "tablet"], p=[0.62, 0.31, 0.07])
        variant = rng.choice(["A", "B"])
        visitor = int(rng.integers(1, 15_000))
        steps = ["landing", "menu", "plan_select", "checkout", "purchase"]
        p_next = {"mobile": [0.62, 0.55, 0.48, 0.52], "desktop": [0.70, 0.62, 0.55, 0.60], "tablet": [0.66, 0.58, 0.5, 0.55]}[device]
        p_next = list(p_next)
        if variant == "B":
            p_next[3] *= 1.12  # new one-page checkout lifts checkout → purchase
        reached = 1
        for p in p_next:
            if rng.random() < p:
                reached += 1
            else:
                break
        t = ts
        for s in steps[:reached]:
            ev.append((sid, visitor, t.strftime("%Y-%m-%d %H:%M:%S"), s, device, variant))
            t += pd.Timedelta(seconds=int(rng.integers(15, 400)))
        sid += 1
    events = pd.DataFrame(ev, columns=["session_id", "visitor_id", "event_time", "event_name", "device", "ab_variant"])

    # --- marketing spend -----------------------------------------------------------
    cpa = {"paid_social": 48, "search": 42, "referral": 15, "tv": 70, "affiliate_voucher": 30}
    months = pd.period_range("2024-01", "2026-06", freq="M")
    signups_m = customers.assign(m=pd.to_datetime(customers.signup_date).dt.to_period("M")) \
        .groupby(["m", "acquisition_channel"]).size()
    spend = [(str(m), ch, round(float(signups_m.get((m, ch), 0) * cpa[ch] * rng.uniform(0.85, 1.15)), 2))
             for m in months for ch in CHANNELS]
    marketing = pd.DataFrame(spend, columns=["month", "channel", "spend_gbp"])

    # --- deliberate data-quality issues ----------------------------------------------
    dup = orders.sample(15, random_state=1)
    orders = pd.concat([orders, dup], ignore_index=True)                 # duplicate order rows
    orders.loc[orders.sample(8, random_state=2).index, "revenue_gbp"] = np.nan  # missing revenue
    orphan = pd.DataFrame([(99_000_000 + i, 999_999, 1) for i in range(5)], columns=["order_id", "customer_id", "plan_id"])
    orphan = orphan.assign(delivery_date="2025-03-03", status="delivered", revenue_gbp=41.99, discount_gbp=0.0)
    orders = pd.concat([orders, orphan[orders.columns]], ignore_index=True)  # orders for unknown customers

    with sqlite3.connect(path) as con:
        con.executescript("""
        CREATE TABLE dim_customers (customer_id INTEGER PRIMARY KEY, signup_date TEXT, region TEXT,
            acquisition_channel TEXT, plan_id INTEGER, age_band TEXT);
        CREATE TABLE dim_plans (plan_id INTEGER PRIMARY KEY, plan_name TEXT, people INTEGER, recipes_per_box INTEGER,
            weekly_price_gbp REAL);
        CREATE TABLE dim_recipes (recipe_id INTEGER PRIMARY KEY, recipe_name TEXT, cuisine TEXT,
            ingredient_cost_gbp REAL, cook_minutes INTEGER);
        CREATE TABLE fact_orders (order_id INTEGER, customer_id INTEGER, delivery_date TEXT, plan_id INTEGER,
            status TEXT, revenue_gbp REAL, discount_gbp REAL);
        CREATE TABLE fact_order_items (order_id INTEGER, recipe_id INTEGER);
        CREATE TABLE fact_cancellations (customer_id INTEGER, cancel_date TEXT, reason TEXT);
        CREATE TABLE fact_events (session_id INTEGER, visitor_id INTEGER, event_time TEXT, event_name TEXT,
            device TEXT, ab_variant TEXT);
        CREATE TABLE fact_marketing (month TEXT, channel TEXT, spend_gbp REAL);
        """)
        customers.to_sql("dim_customers", con, if_exists="append", index=False)
        pd.DataFrame(PLANS, columns=["plan_id", "plan_name", "people", "recipes_per_box", "weekly_price_gbp"]) \
            .to_sql("dim_plans", con, if_exists="append", index=False)
        recipes.to_sql("dim_recipes", con, if_exists="append", index=False)
        orders.to_sql("fact_orders", con, if_exists="append", index=False)
        items.to_sql("fact_order_items", con, if_exists="append", index=False)
        cancellations.to_sql("fact_cancellations", con, if_exists="append", index=False)
        events.to_sql("fact_events", con, if_exists="append", index=False)
        marketing.to_sql("fact_marketing", con, if_exists="append", index=False)
    return path


if __name__ == "__main__":
    p = build()
    with sqlite3.connect(p) as con:
        for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            print(f"{t:22s}", con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
