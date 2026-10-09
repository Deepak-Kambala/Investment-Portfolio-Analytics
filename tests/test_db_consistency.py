import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def test_db_consistency():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM account_cash WHERE cash_balance < -0.01"
        ).fetchone()[0] == 0
        assert conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT account_id, security_id,
                       SUM(CASE transaction_type WHEN 'BUY' THEN quantity ELSE -quantity END) AS quantity
                FROM transactions
                WHERE transaction_type IN ('BUY', 'SELL')
                GROUP BY account_id, security_id
            ) t
            FULL JOIN holdings h USING (account_id, security_id)
            WHERE ROUND(COALESCE(t.quantity, 0), 4) <> ROUND(COALESCE(h.quantity, 0), 4)
        """).fetchone()[0] == 0
        assert conn.execute("""
            SELECT COUNT(*) FROM account_portfolio_value v
            JOIN (
                SELECT h.account_id, SUM(h.quantity * lp.close_price) AS market_value
                FROM holdings h
                JOIN latest_prices lp ON lp.security_id = h.security_id
                GROUP BY h.account_id
            ) expected USING (account_id)
            WHERE ROUND(v.market_value, 4) <> ROUND(expected.market_value, 4)
        """).fetchone()[0] == 0
