# Investment Portfolio & Transaction Analytics

A normalized PostgreSQL database for investment operations (customers, accounts, orders, trades, holdings,
prices, dividends, fees), a synthetic data pipeline, analytical SQL (CTEs, window functions, views), an atomic
trade function, a measured index optimization, and a read-only dashboard that queries the database live.
Deployed on Neon.

```
scripts/generate_data.py ──CSV──▶ scripts/setup_db.py ──▶ Neon PostgreSQL ◀── backend/main.py (FastAPI) ◀── frontend (React)
                                                          tables · views · functions
```

## Layout

```
db/schema/01_tables.sql          9 tables, PK/FK/CHECK/UNIQUE constraints
db/schema/02_indexes.sql         composite index, applied by the benchmark script
db/views/analytics_views.sql     latest_prices, account_positions, account_portfolio_value,
                                 account_cash, daily_security_returns, daily_trading_volume
db/functions/portfolio_functions.sql   execute_trade(): transaction + holdings + fee, atomically
db/queries/                      01 basic/joins/subqueries · 02 CTEs · 03 window functions · 04 trade transaction
scripts/generate_data.py         seeded synthetic data, replays trades in time order
scripts/setup_db.py              create schema, COPY load, views, functions, consistency checks
scripts/benchmark_indexes.py     EXPLAIN ANALYZE before/after index, writes docs/query-optimization.md
backend/main.py                  12 GET endpoints, each one SQL query on a table or view
frontend/                        Vite + React + Recharts: dashboard, portfolio, transactions, analytics
docs/er-diagram.md               ER diagram (Mermaid, renders on GitHub)
```

## Run it

1. Create a Neon project (`investment-portfolio-analytics`, database `investment_db`).
2. `cp .env.example .env` and paste the Neon connection string. `.env` is git-ignored.
3. ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python scripts/generate_data.py --scale small    # develop on small data first
   python scripts/setup_db.py                       # prints two consistency checks, both should be 0
   python scripts/benchmark_indexes.py              # writes docs/query-optimization.md with YOUR numbers
   ```
4. Scale up: `python scripts/generate_data.py --scale full && python scripts/setup_db.py`, then re-run the benchmark.
5. Start the app (two terminals):
   ```bash
   cd backend && uvicorn main:app --reload          # http://localhost:8000/docs
   cd frontend && npm install && npm run dev        # http://localhost:5173
   ```

## Screens and the SQL behind them

| Screen | Endpoint | Source |
|---|---|---|
| Dashboard: AUM, portfolio value, cash, accounts, volume, buy vs sell, fees, dividends | `/api/summary` | `account_portfolio_value`, `account_cash`, `transactions`, `fees` |
| Portfolio: holdings, avg cost, price, market value, unrealized P/L | `/api/portfolio/{id}` | `account_positions` |
| Transactions: filter by account, security, type, date range | `/api/transactions` | `transactions` (parameterized WHERE) |
| Analytics | `/api/analytics/*` | `daily_trading_volume`, `daily_security_returns`, `account_portfolio_value`, `fees`, `transactions` |

AUM = securities market value + cash. Portfolio value = securities market value only.

## Design decisions (be ready to explain these)

- **NUMERIC, not FLOAT**: binary floating point cannot represent 0.1 exactly; money needs exact decimals.
- **Identity is `BY DEFAULT`**: lets `COPY` load explicit ids; `setup_db.py` then resets each sequence with `setval`.
- **`holdings` is derived state**: it must equal sum(BUY) - sum(SELL) per account and security. `setup_db.py` verifies this.
- **Cash is not stored**: `account_cash` computes it from the ledger (deposits + sells + dividends - withdrawals - buys - fees).
- **Fees are rows in `fees`**, linked to the trade, so there is no `FEE` transaction type.
- **Average cost** is the weighted average of buys and excludes fees; sells do not change it.
- **Latest price**, not today's: `DISTINCT ON (security_id) ... ORDER BY price_date DESC`, because today's price may not exist.
- **Dividends** are paid on the shares held at the ex-date (snapshot taken when the generator replays the timeline).
- **`execute_trade()`** checks cash (BUY) or shares (SELL, with `FOR UPDATE` row lock), then writes transaction, holdings and fee in one atomic unit.
- **Index**: `(account_id, transaction_date)`: equality column first, range column second. Measured, not assumed.
- **API is read-only** and every value reaches SQL as a bound parameter (no string-built filters).

## Known simplifications

Synthetic data and random-walk prices; one currency; no corporate actions, taxes, margin or settlement delay; no authentication.
