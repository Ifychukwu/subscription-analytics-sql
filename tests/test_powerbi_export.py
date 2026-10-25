"""The Power BI export: row counts match the database, keys are unique, no orphan foreign keys."""
import re
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from harvest.build_db import build
from harvest.export_powerbi import DESCRIPTIONS, PRIMARY_KEYS, RELATIONSHIPS, export
from harvest.run import SQL_DIR, connect, run_file

ROOT = Path(__file__).resolve().parents[1]
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pbi")
    db = build(tmp / "harvest_test.db", n_customers=800, seed=5)
    out = tmp / "powerbi"
    export(db, out)
    csvs = {p.stem: pd.read_csv(p) for p in out.glob("*.csv")}
    raw = sqlite3.connect(db)
    yield db, out, csvs, raw
    raw.close()


def count(raw, sql):
    return raw.execute(sql).fetchone()[0]


def test_all_tables_written(exported):
    _, out, csvs, _ = exported
    assert set(csvs) == set(PRIMARY_KEYS)
    assert (out / "data_dictionary.md").exists()


def test_row_counts_match_database(exported):
    db, _, csvs, raw = exported
    assert len(csvs["dim_customer"]) == count(raw, "SELECT COUNT(*) FROM dim_customers")
    assert len(csvs["dim_plan"]) == count(raw, "SELECT COUNT(*) FROM dim_plans")
    assert len(csvs["dim_recipe"]) == count(raw, "SELECT COUNT(*) FROM dim_recipes")
    assert len(csvs["dim_channel"]) == count(raw, "SELECT COUNT(DISTINCT acquisition_channel) FROM dim_customers")
    assert len(csvs["fact_cancellations"]) == count(raw, "SELECT COUNT(*) FROM fact_cancellations")
    assert len(csvs["fact_marketing_spend"]) == count(raw, "SELECT COUNT(*) FROM fact_marketing")
    assert len(csvs["fact_web_sessions"]) == count(raw, "SELECT COUNT(DISTINCT session_id) FROM fact_events")

    # orders: independent pandas cleaning of the raw table (dedupe, known customers, revenue present)
    o = pd.read_sql("SELECT rowid AS rid, * FROM fact_orders", raw).sort_values("rid").drop_duplicates("order_id")
    cust = pd.read_sql("SELECT customer_id FROM dim_customers", raw).customer_id
    o = o[o.customer_id.isin(cust) & o.revenue_gbp.notna()]
    assert len(csvs["fact_orders"]) == len(o)
    items = pd.read_sql("SELECT * FROM fact_order_items", raw)
    assert len(csvs["fact_order_items"]) == items.order_id.isin(o.order_id).sum()

    # delivered boxes in the export are exactly the case study's cleaned view
    con = connect(db)
    run_file(con, SQL_DIR / "02_clean_orders_view.sql")
    assert csvs["fact_orders"].is_delivered.sum() == count(con, "SELECT COUNT(*) FROM v_orders")
    con.close()


def test_primary_keys_unique_and_not_null(exported):
    _, _, csvs, _ = exported
    for table, keys in PRIMARY_KEYS.items():
        df = csvs[table]
        assert df[keys].notna().all().all(), table
        assert not df.duplicated(keys).any(), table


def test_no_orphan_foreign_keys(exported):
    _, _, csvs, _ = exported
    for fact, fk, dim, pk, _active in RELATIONSHIPS:
        values = csvs[fact][fk].dropna()
        orphans = set(values) - set(csvs[dim][pk])
        assert not orphans, f"{fact}.{fk} -> {dim}.{pk}: {sorted(orphans)[:5]}"


def test_date_dimension_is_contiguous_and_covers_facts(exported):
    _, _, csvs, _ = exported
    d = pd.to_datetime(csvs["dim_date"]["date"])
    assert d.is_monotonic_increasing and (d.diff().dropna() == pd.Timedelta(days=1)).all()
    assert (csvs["dim_date"].date_key == d.dt.strftime("%Y%m%d").astype(int)).all()


def test_csv_hygiene(exported):
    _, out, csvs, _ = exported
    for name, df in csvs.items():
        assert not any(c.startswith("Unnamed") or c == "index" for c in df.columns), name
        assert list(df.columns) == list(DESCRIPTIONS[name]), f"{name}: undocumented or missing columns"
        for col in df.columns:
            if col.endswith("_date") or col in ("date", "cohort_month"):
                assert df[col].dropna().astype(str).str.match(ISO_DATE).all(), f"{name}.{col}"
    # integer columns with blanks must not be written as floats ("3.0")
    raw_text = pd.read_csv(out / "fact_orders.csv", dtype=str)
    assert not raw_text.months_since_first_box.dropna().str.contains(r"\.").any()


def test_ltv_to_cac_from_csvs_matches_sql(exported):
    """The DAX measure LTV:CAC = gross margin / spend, by channel, must reproduce Q6."""
    db, _, csvs, _ = exported
    con = connect(db)
    run_file(con, SQL_DIR / "02_clean_orders_view.sql")
    q6 = run_file(con, SQL_DIR / "06_ltv_vs_cac_by_channel.sql").set_index("acquisition_channel").ltv_to_cac
    con.close()
    o, c, ch = csvs["fact_orders"], csvs["dim_customer"], csvs["dim_channel"]
    margin = o[o.is_delivered == 1].merge(c, on="customer_id").groupby("channel_id").gross_margin_gbp.sum()
    spend = csvs["fact_marketing_spend"].groupby("channel_id").spend_gbp.sum()
    got = (margin / spend).rename(ch.set_index("channel_id").channel_code)
    for channel, value in q6.items():
        assert got[channel] == pytest.approx(value, abs=0.006)


def test_committed_csvs_are_small_enough_for_github():
    for p in (ROOT / "powerbi").glob("*.csv"):
        assert p.stat().st_size < 25 * 1024 * 1024, p.name
