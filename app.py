"""Harvest Box SQL explorer: pick a business question, read the SQL, see the answer.

Run:  PYTHONPATH=src streamlit run app.py
(builds data/harvest.db on first run, ~30 s)
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from harvest.build_db import DB, build  # noqa: E402
from harvest.run import SQL_DIR, connect, optimisation_demo, question, run_file  # noqa: E402

st.set_page_config(page_title="Harvest Box SQL case study", page_icon="🥕", layout="wide")


@st.cache_resource(show_spinner="Building the warehouse (first run only)…")
def ensure_db() -> Path:
    if not DB.exists():
        build()
    con = connect(DB)
    run_file(con, SQL_DIR / "02_clean_orders_view.sql")   # every analysis uses the clean view
    con.close()
    return DB


# SQLite connections can't be shared across Streamlit's threads, so open one per rerun.
db = ensure_db()
con = connect(db)
files = sorted(SQL_DIR.glob("*.sql"))
st.title("🥕 Harvest Box: SQL analytics case study")
st.caption("Fictional UK meal-kit subscription business · synthetic data · SQLite")

tab_q, tab_free, tab_pbi = st.tabs(["Business questions", "Run your own query", "Power BI export"])

with tab_q:
    path = st.selectbox("Question", files, format_func=question)
    left, right = st.columns([1, 1])
    with left:
        st.code(path.read_text(), language="sql")
    with right:
        df = optimisation_demo(con, path) if path.name.startswith("15") else run_file(con, path)
        st.dataframe(df, use_container_width=True, hide_index=True)
        fig = ROOT / "reports" / "figures"
        for key, img in {"03": "monthly_revenue", "04": "cohort_retention", "06": "ltv_cac",
                         "09": "recipe_pareto", "10": "funnel"}.items():
            if path.name.startswith(key) and (fig / f"{img}.png").exists():
                st.image(str(fig / f"{img}.png"))

with tab_free:
    st.write("Read-only: one `SELECT` statement against the warehouse (tables `dim_*`, `fact_*`, view `v_orders`).")
    sql = st.text_area("SQL", "SELECT acquisition_channel, COUNT(*) AS customers\nFROM dim_customers\nGROUP BY 1\nORDER BY 2 DESC;")
    if st.button("Run", type="primary"):
        if not sql.lstrip().lower().startswith(("select", "with")) or ";" in sql.strip().rstrip(";"):
            st.error("Only a single SELECT (or WITH … SELECT) statement is allowed.")
        else:
            try:
                ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)   # read-only connection
                try:
                    st.dataframe(pd.read_sql_query(sql, ro).head(1000), use_container_width=True, hide_index=True)
                finally:
                    ro.close()
            except Exception as e:  # show SQL errors to the user
                st.error(str(e))

with tab_pbi:
    readme = ROOT / "powerbi" / "README.md"
    st.markdown(readme.read_text() if readme.exists() else "Run `python -m harvest.export_powerbi` first.")
