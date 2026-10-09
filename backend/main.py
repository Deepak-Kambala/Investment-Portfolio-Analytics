"""Read-only API over the PostgreSQL analytics layer. Every endpoint is one SQL query against a table or view."""
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg import OperationalError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Neon pooler endpoints reject statement_timeout startup options, so use the
# matching direct endpoint for the API pool when the configured URL is pooled.
database_url = os.environ["DATABASE_URL"].replace("-pooler.", ".", 1)
# check= re-validates a connection before use (Neon closes idle connections when it scales to zero).
pool = ConnectionPool(database_url, min_size=1, max_size=10, timeout=15, open=False,
                      kwargs={"row_factory": dict_row, "options": "-c statement_timeout=10000"},
                      check=ConnectionPool.check_connection)


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Portfolio analytics API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET"], allow_headers=["*"])


def rows(sql: str, params: dict | None = None) -> list[dict]:
    try:
        with pool.connection() as conn:
            return conn.execute(sql, params or {}).fetchall()
    except (PoolTimeout, OperationalError):
        raise HTTPException(503, "Database busy or unavailable")


@app.get("/api/health")
def health():
    rows("SELECT 1")
    return {"status": "ok"}


@app.get("/api/summary")
def summary():
    r = rows("""
        SELECT (SELECT COUNT(*) FROM accounts WHERE status = 'ACTIVE')                    AS accounts,
               (SELECT COALESCE(SUM(market_value), 0) FROM account_portfolio_value)       AS portfolio_value,
               (SELECT COALESCE(SUM(cash_balance), 0) FROM account_cash)                  AS cash,
               (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE transaction_type = 'BUY')  AS buy_volume,
               (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE transaction_type = 'SELL') AS sell_volume,
               (SELECT COALESCE(SUM(amount), 0) FROM fees)                                AS fees_paid,
               (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE transaction_type = 'DIVIDEND') AS dividend_income
    """)[0]
    r["aum"] = r["portfolio_value"] + r["cash"]
    r["total_volume"] = r["buy_volume"] + r["sell_volume"]
    return r


@app.get("/api/accounts")
def top_accounts():
    """Top 100 accounts by portfolio value, used to pick an account on the portfolio page."""
    return rows("""
        SELECT a.account_id, c.full_name, a.account_type, v.market_value
        FROM account_portfolio_value v
        JOIN accounts a  ON a.account_id  = v.account_id
        JOIN customers c ON c.customer_id = a.customer_id
        ORDER BY v.market_value DESC LIMIT 100""")


@app.get("/api/securities")
def securities():
    return rows("SELECT security_id, symbol, security_name FROM securities ORDER BY symbol")


@app.get("/api/portfolio/{account_id}")
def portfolio(account_id: int):
    acct = rows("""
        SELECT a.account_id, c.full_name, a.account_type, a.status, k.cash_balance
        FROM accounts a
        JOIN customers c   ON c.customer_id = a.customer_id
        JOIN account_cash k ON k.account_id = a.account_id
        WHERE a.account_id = %(id)s""", {"id": account_id})
    if not acct:
        raise HTTPException(404, "Account not found")
    positions = rows("""
        SELECT symbol, security_name, quantity, average_cost, current_price, market_value, cost_basis, unrealized_pl
        FROM account_positions WHERE account_id = %(id)s ORDER BY market_value DESC""", {"id": account_id})
    totals = rows("""
        SELECT COALESCE(SUM(market_value), 0) AS market_value,
               COALESCE(SUM(cost_basis), 0)   AS cost_basis,
               COALESCE(SUM(unrealized_pl), 0) AS unrealized_pl
        FROM account_positions WHERE account_id = %(id)s""", {"id": account_id})[0]
    return {"account": acct[0], "totals": totals, "positions": positions}


@app.get("/api/transactions")
def transactions(account_id: int | None = None, security_id: int | None = None,
                 transaction_type: str | None = Query(None, pattern="^(BUY|SELL|DIVIDEND|DEPOSIT|WITHDRAWAL)$"),
                 date_from: date | None = None, date_to: date | None = None,
                 limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    where, p = [], {"limit": limit, "offset": offset}
    if account_id is not None:
        where.append("t.account_id = %(account_id)s"); p["account_id"] = account_id
    if security_id is not None:
        where.append("t.security_id = %(security_id)s"); p["security_id"] = security_id
    if transaction_type:
        where.append("t.transaction_type = %(transaction_type)s"); p["transaction_type"] = transaction_type
    if date_from:
        where.append("t.transaction_date >= %(date_from)s"); p["date_from"] = date_from
    if date_to:  # inclusive of the whole end day
        where.append("t.transaction_date < %(date_to)s::date + 1"); p["date_to"] = date_to
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = rows(f"SELECT COUNT(*) AS n FROM transactions t {clause}", p)[0]["n"]
    data = rows(f"""
        SELECT t.transaction_id, t.account_id, s.symbol, t.transaction_type, t.quantity, t.price, t.amount, t.transaction_date
        FROM transactions t LEFT JOIN securities s ON s.security_id = t.security_id
        {clause}
        ORDER BY t.transaction_date DESC, t.transaction_id DESC
        LIMIT %(limit)s OFFSET %(offset)s""", p)
    return {"total": total, "rows": data}


@app.get("/api/analytics/top-customers")
def top_customers():
    return rows("""
        SELECT c.customer_id, c.full_name, COUNT(*) AS trades, SUM(t.amount) AS volume
        FROM transactions t
        JOIN accounts a  ON a.account_id  = t.account_id
        JOIN customers c ON c.customer_id = a.customer_id
        WHERE t.transaction_type IN ('BUY', 'SELL')
        GROUP BY c.customer_id, c.full_name ORDER BY volume DESC LIMIT 10""")


@app.get("/api/analytics/most-traded")
def most_traded():
    return rows("""
        SELECT s.symbol, COUNT(*) AS trades, SUM(t.amount) AS volume
        FROM transactions t JOIN securities s ON s.security_id = t.security_id
        WHERE t.transaction_type IN ('BUY', 'SELL')
        GROUP BY s.symbol ORDER BY trades DESC, volume DESC LIMIT 10""")


@app.get("/api/analytics/daily-volume")
def daily_volume():
    return rows("""
        SELECT * FROM (SELECT trade_date, buy_volume, sell_volume FROM daily_trading_volume
                       ORDER BY trade_date DESC LIMIT 90) x
        ORDER BY trade_date""")


@app.get("/api/analytics/performance")
def performance():
    """Five best and five worst accounts by unrealized return."""
    return rows("""
        SELECT * FROM (
            (SELECT account_id, market_value, unrealized_pl, return_pct FROM account_portfolio_value
             ORDER BY return_pct DESC NULLS LAST LIMIT 5)
            UNION ALL
            (SELECT account_id, market_value, unrealized_pl, return_pct FROM account_portfolio_value
             ORDER BY return_pct ASC NULLS LAST LIMIT 5)
        ) x ORDER BY return_pct DESC""")


@app.get("/api/analytics/returns/{security_id}")
def security_returns(security_id: int):
    return rows("""
        SELECT * FROM (SELECT price_date, close_price, daily_return_pct FROM daily_security_returns
                       WHERE security_id = %(id)s AND daily_return_pct IS NOT NULL
                       ORDER BY price_date DESC LIMIT 120) x
        ORDER BY price_date""", {"id": security_id})


@app.get("/api/analytics/fees")
def fees():
    return {
        "by_type": rows("SELECT fee_type, COUNT(*) AS count, SUM(amount) AS total FROM fees GROUP BY fee_type ORDER BY total DESC"),
        "by_month": rows("""
            SELECT to_char(date_trunc('month', t.transaction_date), 'YYYY-MM') AS month, SUM(f.amount) AS total
            FROM fees f JOIN transactions t ON t.transaction_id = f.transaction_id
            GROUP BY 1 ORDER BY 1"""),
    }


@app.get("/api/analytics/dividends")
def dividends():
    return rows("""
        SELECT to_char(date_trunc('month', transaction_date), 'YYYY-MM') AS month, SUM(amount) AS total
        FROM transactions WHERE transaction_type = 'DIVIDEND' GROUP BY 1 ORDER BY 1""")
