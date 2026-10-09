"""Create the schema in Neon, load data/*.csv with COPY, build views + functions, run sanity checks.

    python scripts/setup_db.py
Re-running drops and recreates all tables.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

LOAD_ORDER = ["customers", "accounts", "securities", "market_prices", "dividends",
              "orders", "transactions", "holdings", "fees"]
ID_COLUMN = {"customers": "customer_id", "accounts": "account_id", "securities": "security_id",
             "orders": "order_id", "transactions": "transaction_id", "holdings": "holding_id",
             "dividends": "dividend_id", "fees": "fee_id"}

CHECKS = {
    "accounts with negative cash (expect 0)":
        "SELECT COUNT(*) FROM account_cash WHERE cash_balance < -0.01",
    "holdings that do not equal buys - sells (expect 0)": """
        SELECT COUNT(*) FROM (
            SELECT account_id, security_id,
                   SUM(CASE transaction_type WHEN 'BUY' THEN quantity ELSE -quantity END) AS q
            FROM transactions WHERE transaction_type IN ('BUY', 'SELL') GROUP BY 1, 2
        ) t FULL JOIN holdings h USING (account_id, security_id)
        WHERE ROUND(COALESCE(t.q, 0), 4) <> ROUND(COALESCE(h.quantity, 0), 4)""",
}


def run_file(conn, path):
    conn.execute((ROOT / path).read_text())


def main():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("DROP TABLE IF EXISTS " + ", ".join(reversed(LOAD_ORDER)) + " CASCADE")
        run_file(conn, "db/schema/01_tables.sql")

        for table in LOAD_ORDER:
            csv = ROOT / "data" / f"{table}.csv"
            cols = csv.open().readline().strip()
            with csv.open() as f, conn.cursor().copy(
                    f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
                while chunk := f.read(1 << 20):
                    cp.write(chunk)
            print(f"loaded {table}")

        for table, col in ID_COLUMN.items():   # identity sequences must continue after the loaded ids
            conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), (SELECT MAX({col}) FROM {table}))")

        run_file(conn, "db/views/analytics_views.sql")
        run_file(conn, "db/functions/portfolio_functions.sql")
        conn.commit()
        conn.autocommit = True
        conn.execute("ANALYZE")

        for label, sql in CHECKS.items():
            print(f"check: {label}: {conn.execute(sql).fetchone()[0]}")


if __name__ == "__main__":
    main()
