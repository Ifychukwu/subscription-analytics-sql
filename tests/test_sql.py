"""Every SQL answer is checked against an independent pandas calculation."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from harvest.build_db import build
from harvest.run import SQL_DIR, connect, optimisation_demo, run_file, split_statements


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    db = build(tmp_path_factory.mktemp("db") / "harvest_test.db", n_customers=1500, seed=3)
    c = connect(db)
    run_file(c, SQL_DIR / "02_clean_orders_view.sql")  # creates v_orders
    yield c
    c.close()


def sql(con, name):
    return run_file(con, next(SQL_DIR.glob(f"{name}*.sql")))


def clean_orders(con) -> pd.DataFrame:
    o = pd.read_sql("SELECT rowid AS rid, * FROM fact_orders", con)
    cust = pd.read_sql("SELECT customer_id FROM dim_customers", con)
    o = o[o.customer_id.isin(cust.customer_id)].sort_values("rid").drop_duplicates("order_id")
    return o[o.revenue_gbp.notna() & (o.status == "delivered")]


def test_split_statements_handles_semicolons_in_strings():
    assert len(split_statements("SELECT ';' AS a;\nSELECT 2;")) == 2


def test_data_quality_finds_planted_problems(con):
    r = sql(con, "01").set_index("check_name")["failing_rows"]
    assert r["duplicate order rows"] == 15
    assert r["orders with missing revenue"] == 8
    assert r["orders for unknown customers"] == 5


def test_clean_view_matches_pandas(con):
    assert pd.read_sql("SELECT COUNT(*) n FROM v_orders", con).n[0] == len(clean_orders(con))


def test_monthly_revenue_matches_pandas(con):
    got = sql(con, "03").set_index("month")["revenue_gbp"]
    o = clean_orders(con)
    exp = o.groupby(o.delivery_date.str[:7]).revenue_gbp.sum().round(2)
    pd.testing.assert_series_equal(got, exp, check_names=False, atol=0.01)


def test_mom_growth_uses_previous_month(con):
    r = sql(con, "03")
    expected = round(100 * (r.revenue_gbp[5] - r.revenue_gbp[4]) / r.revenue_gbp[4], 1)
    assert r.mom_growth_pct[5] == pytest.approx(expected, abs=0.11)


def test_cohort_month_zero_is_100(con):
    r = sql(con, "04")
    assert (r[r.month_number == 0].retention_pct == 100).all()
    assert (r[r.month_number > 0].retention_pct <= 100).all()


def test_rfm_shares_sum_to_100(con):
    r = sql(con, "07")
    assert r.pct_customers.sum() == pytest.approx(100, abs=0.5)
    assert r.pct_revenue.sum() == pytest.approx(100, abs=0.5)


def test_pareto_running_total_reaches_100(con):
    r = sql(con, "09")
    assert r.cumulative_share_pct.iloc[-1] == pytest.approx(100, abs=0.1)
    assert r.cumulative_share_pct.is_monotonic_increasing


def test_funnel_matches_pandas(con):
    r = sql(con, "10").set_index("device")
    ev = pd.read_sql("SELECT * FROM fact_events", con)
    s = ev.pivot_table(index="session_id", columns="event_name", values="event_time", aggfunc="count").notna()
    dev = ev.groupby("session_id").device.first()
    mob = s[dev == "mobile"]
    assert r.loc["mobile", "sessions"] == mob.landing.sum()
    assert r.loc["mobile", "overall_conversion_pct"] == pytest.approx(round(100 * mob.purchase.sum() / mob.landing.sum(), 2))


def test_ab_test_z_score_matches_formula(con):
    r = sql(con, "11").iloc[0]
    ev = pd.read_sql("SELECT * FROM fact_events", con)
    s = ev.groupby("session_id").agg(v=("ab_variant", "max"), c=("event_name", lambda x: "checkout" in set(x)),
                                     p=("event_name", lambda x: "purchase" in set(x)))
    s = s[s.c]
    a, b = s[s.v == "A"], s[s.v == "B"]
    pa, pb = a.p.mean(), b.p.mean()
    pool = s.p.mean()
    z = (pb - pa) / np.sqrt(pool * (1 - pool) * (1 / len(a) + 1 / len(b)))
    assert r.z_score == pytest.approx(round(z, 2), abs=0.011)
    assert r.n_a == len(a) and r.n_b == len(b)


def test_sessionization_never_exceeds_logged(con):
    r = sql(con, "12").iloc[0]
    assert 0.95 * r.logged_sessions <= r.reconstructed_sessions <= r.logged_sessions


def test_percentiles_are_ordered(con):
    r = sql(con, "13")
    assert r.spend_gbp.is_monotonic_increasing


def test_index_changes_plan_and_speeds_up(con):
    r = optimisation_demo(con, SQL_DIR / "15_query_optimisation.sql").set_index("version")
    assert "SCAN" in r.loc["without index", "query_plan"]
    assert "COVERING INDEX" in r.loc["with index", "query_plan"]


def test_every_sql_file_runs(con):
    for path in sorted(SQL_DIR.glob("*.sql")):
        if path.name.startswith("15"):
            continue
        assert len(run_file(con, path)) > 0, path.name
