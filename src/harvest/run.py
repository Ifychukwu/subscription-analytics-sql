"""Run every analysis in sql/ against the warehouse, save results and charts.

Usage:  python -m harvest.run        (builds data/harvest.db first if missing)
"""
from __future__ import annotations

import math
import re
import sqlite3
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from harvest.build_db import DB, build  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR, RESULTS, FIGS = ROOT / "sql", ROOT / "results", ROOT / "reports" / "figures"


def connect(path=DB) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    # Some SQLite builds ship without math functions; register them if missing.
    for name, fn, n in [("sqrt", math.sqrt, 1), ("ln", math.log, 1), ("power", math.pow, 2)]:
        try:
            con.execute(f"SELECT {name}({', '.join(['1'] * n)})")
        except sqlite3.OperationalError:
            con.create_function(name, n, fn)
    return con


def split_statements(sql: str) -> list[str]:
    """Split a script into complete statements (handles ';' inside strings)."""
    stmts, buf = [], ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip() and not all(l.strip().startswith("--") or not l.strip() for l in buf.splitlines()):
                stmts.append(buf.strip())
            buf = ""
    return stmts


def run_file(con: sqlite3.Connection, path: Path) -> pd.DataFrame:
    stmts = split_statements(path.read_text())
    for s in stmts[:-1]:
        con.execute(s)
    return pd.read_sql_query(stmts[-1], con)


def question(path: Path) -> str:
    first = path.read_text().splitlines()[0]
    return re.sub(r"^--\s*", "", first)


def optimisation_demo(con: sqlite3.Connection, path: Path) -> pd.DataFrame:
    text = path.read_text()
    index_sql = re.search(r"-- @index:\s*(.+)", text).group(1)
    query = split_statements(text)[-1]
    con.execute("DROP INDEX IF EXISTS idx_orders_customer_date")
    rows = []
    for label in ("without index", "with index"):
        if label == "with index":
            con.execute(index_sql)
        plan = " | ".join(r[-1] for r in con.execute("EXPLAIN QUERY PLAN " + query))
        t0 = time.perf_counter()
        for _ in range(20):
            con.execute(query).fetchall()
        ms = (time.perf_counter() - t0) / 20 * 1000
        rows.append({"version": label, "query_plan": plan, "avg_ms": round(ms, 2)})
    return pd.DataFrame(rows)


def charts(res: dict[str, pd.DataFrame]):
    FIGS.mkdir(parents=True, exist_ok=True)

    m = res["03"]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(m["month"], m["revenue_gbp"] / 1000, marker="o", ms=3)
    ax.set(title="Monthly revenue (£k)", ylabel="£k")
    ax.set_xticks(m["month"][::3]); ax.tick_params(axis="x", rotation=45)
    fig.tight_layout(); fig.savefig(FIGS / "monthly_revenue.png", dpi=130); plt.close(fig)

    c = res["04"].pivot(index="cohort", columns="month_number", values="retention_pct")
    c = c[c.index <= "2025-06"]
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(c.values, cmap="Greens", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(c.shape[1]), c.columns); ax.set_yticks(range(c.shape[0]), c.index)
    for i in range(c.shape[0]):
        for j in range(c.shape[1]):
            v = c.values[i, j]
            if not math.isnan(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7, color="white" if v > 60 else "black")
    ax.set(xlabel="Months since first box", ylabel="Cohort (first box month)", title="Cohort retention (%)")
    fig.colorbar(im, ax=ax, fraction=0.03); fig.tight_layout(); fig.savefig(FIGS / "cohort_retention.png", dpi=130)
    plt.close(fig)

    ch = res["06"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.barh(ch["acquisition_channel"], ch["ltv_to_cac"], color=["#2e7d32" if v >= 3 else "#c62828" if v < 1 else "#f9a825"
                                                                for v in ch["ltv_to_cac"]])
    ax.axvline(3, ls="--", color="grey"); ax.text(3.05, -0.4, "3:1 rule of thumb", fontsize=8)
    ax.set(xlabel="Lifetime gross margin ÷ acquisition cost", title="LTV:CAC by channel")
    fig.tight_layout(); fig.savefig(FIGS / "ltv_cac.png", dpi=130); plt.close(fig)

    p = res["09"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(range(len(p)), p["share_pct"], color="#5c6bc0")
    ax2 = ax.twinx(); ax2.plot(range(len(p)), p["cumulative_share_pct"], color="#c62828")
    ax2.axhline(80, ls="--", color="grey", lw=1)
    ax.set(xlabel="Recipes ranked by demand", ylabel="share of demand %", title="Recipe demand: Pareto chart")
    ax2.set_ylabel("cumulative %"); fig.tight_layout(); fig.savefig(FIGS / "recipe_pareto.png", dpi=130); plt.close(fig)

    f = res["10"].set_index("device")
    steps = ["landing_to_menu_pct", "menu_to_plan_pct", "plan_to_checkout_pct", "checkout_to_purchase_pct"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    f[steps].T.plot.bar(ax=ax); ax.set_xticklabels(["landing→menu", "menu→plan", "plan→checkout", "checkout→purchase"], rotation=0)
    ax.set(ylabel="step conversion %", title="Funnel step conversion by device")
    fig.tight_layout(); fig.savefig(FIGS / "funnel.png", dpi=130); plt.close(fig)


def main() -> dict[str, pd.DataFrame]:
    if not DB.exists():
        build()
    RESULTS.mkdir(exist_ok=True)
    con = connect()
    res = {}
    for path in sorted(SQL_DIR.glob("*.sql")):
        key = path.name[:2]
        df = optimisation_demo(con, path) if key == "15" else run_file(con, path)
        con.commit()
        df.to_csv(RESULTS / f"{path.stem}.csv", index=False)
        res[key] = df
        print(f"\n## {question(path)}\n{df.head(12).to_string(index=False)}")
    charts(res)
    con.close()
    return res


if __name__ == "__main__":
    main()
