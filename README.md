# Project guide: Investment Portfolio & Transaction Analytics

Everything about this project in one place: why it exists, how the pieces fit, where each piece of code lives, how the data is stored in Neon, and how a real company would run something like it.

Put this file at `docs/PROJECT_GUIDE.md` in the repo.

---

## 1. Purpose

Investment firms run on a few questions that are answered from a database:

- What does each customer own right now, and what is it worth?
- Did they make or lose money on it?
- How much trading happened, how much did it cost in fees, and how much dividend income came in?
- Can we trust the numbers (do positions match the trade history)?

This project builds the **data layer that answers those questions**, plus a **read-only internal dashboard** that proves the database really drives the numbers.

The point of the project is the database work, not the UI:

| Skill shown | Where |
|---|---|
| Relational design with keys and constraints | `db/schema/01_tables.sql` |
| Realistic, internally consistent test data | `scripts/generate_data.py` |
| Analytical SQL: joins, CTEs, window functions | `db/queries/`, `db/views/` |
| Atomic multi-table writes | `db/functions/portfolio_functions.sql` |
| Measured performance tuning | `scripts/benchmark_indexes.py` |
| Cloud deployment | Neon PostgreSQL |
| Serving data to an application | `backend/main.py`, `frontend/` |

---

## 2. Big picture

```
 BUILD TIME (run once, or whenever you want fresh data)

 scripts/generate_data.py          scripts/setup_db.py
 ┌───────────────────────┐  CSV   ┌──────────────────────────────┐
 │ simulate customers,   │ ─────▶ │ 1. drop + create tables      │
 │ prices, trades,       │ data/  │ 2. COPY the CSVs in          │
 │ dividends, fees       │        │ 3. reset id sequences        │
 └───────────────────────┘        │ 4. create views + function   │
                                  │ 5. ANALYZE + consistency check│
                                  └──────────────┬───────────────┘
                                                 ▼
                                    ┌─────────────────────────┐
                                    │   Neon PostgreSQL       │
                                    │   tables · views · fn   │
                                    └────────────┬────────────┘
                                                 │
 RUN TIME (every page view)                      │ SQL over SSL
                                                 ▼
 Browser ──▶ React (Vite) ──▶ /api/... ──▶ FastAPI ──▶ one SQL query ──▶ JSON ──▶ tables / charts
```

Three layers, each with one job:

1. **Database** owns the data, the rules (constraints) and the calculations (views).
2. **API** translates an HTTP request into one SQL query and returns JSON. It has no business logic of its own.
3. **UI** shows the result. It never touches the database directly.

Keeping the calculations in SQL views (not in Python or JavaScript) means any other tool, such as a notebook, BI tool or another service, gets the same numbers.

---

## 3. Repository map

```
investment-portfolio-analytics/
├── db/
│   ├── schema/
│   │   ├── 01_tables.sql          9 tables with PK, FK, CHECK, UNIQUE constraints
│   │   └── 02_indexes.sql         composite index on transactions (added by the benchmark)
│   ├── views/analytics_views.sql  the analytical layer (6 views)
│   ├── functions/portfolio_functions.sql   execute_trade(): atomic trade posting
│   └── queries/                   example SQL to run by hand and talk through
│       ├── 01_basic.sql           aggregates, joins, anti-join, subquery
│       ├── 02_ctes.sql            CTEs, sector exposure
│       ├── 03_window_functions.sql   running totals, LAG returns, RANK
│       └── 04_trade_transaction.sql  BEGIN / trade / error / ROLLBACK demo
├── scripts/
│   ├── generate_data.py           synthetic data simulation → data/*.csv
│   ├── setup_db.py                create schema, load, views, function, checks
│   └── benchmark_indexes.py       EXPLAIN ANALYZE before/after → docs/query-optimization.md
├── backend/main.py                FastAPI app, 12 read-only GET endpoints
├── frontend/
│   ├── vite.config.js             dev server + proxy of /api to FastAPI
│   └── src/
│       ├── App.jsx                shell, sidebar, hash routing between pages
│       ├── api.js                 fetch helper, useApi hook, number formatters
│       ├── ui.jsx                 Panel, Stat, DataTable, chart helpers
│       ├── styles.css             the pixel theme
│       └── pages/                 Dashboard, Portfolio, Transactions, Analytics
├── docs/                          er-diagram.md, query-optimization.md (generated), this guide
├── data/                          generated CSVs (git-ignored)
├── .env.example                   template for the connection string
└── requirements.txt
```

---

## 4. Data model

### 4.1 Tables and what each row means

| Table | One row is... | Key columns |
|---|---|---|
| `customers` | a person who owns accounts | `customer_id`, `email` (unique), `risk_profile` (LOW/MEDIUM/HIGH) |
| `accounts` | one account of a customer | `account_type` (BROKERAGE/RETIREMENT/CASH), `status` |
| `securities` | something that can be traded | `symbol` (unique), `asset_type` (STOCK/ETF/BOND/MUTUAL_FUND), `sector` |
| `orders` | an instruction to trade | `side`, `quantity`, `order_type`, `order_status` (FILLED/CANCELLED/REJECTED) |
| `transactions` | a ledger entry: a trade, dividend or cash movement | `transaction_type`, `quantity`, `price`, `amount`, `transaction_date` |
| `holdings` | what an account currently owns of one security | `quantity`, `average_cost` |
| `market_prices` | one security's OHLC prices and volume on one day | primary key `(security_id, price_date)` |
| `dividends` | a dividend event for a security | `ex_date`, `payment_date`, `dividend_per_share` |
| `fees` | a charge attached to one trade | `transaction_id`, `fee_type`, `amount` |

### 4.2 Relationships

```
customers 1──* accounts 1──* orders        *──1 securities
                       1──* transactions   *──1 securities
                       1──* holdings       *──1 securities
securities 1──* market_prices
securities 1──* dividends
transactions 1──* fees
```

The ER diagram is in `docs/er-diagram.md`.

### 4.3 Rules the database enforces (so bad data cannot get in)

- Foreign keys: no account without a customer, no trade for a security that does not exist.
- `CHECK` constraints: valid enum values, `quantity > 0` on orders, `amount >= 0`, `holdings.quantity >= 0`.
- `UNIQUE (account_id, security_id)` on holdings: one row per account and security.
- A trade or dividend must reference a security; a deposit or withdrawal must not.
- `NUMERIC` for every money and quantity column. Floating point cannot represent 0.1 exactly and errors accumulate across thousands of operations.

### 4.4 Which data is "source of truth" and which is derived

| Kind | Tables / views | Note |
|---|---|---|
| Source of truth | `transactions`, `fees`, `market_prices`, `dividends` | the facts that happened |
| Derived, stored | `holdings` | must equal sum(BUY) − sum(SELL) per account and security. `setup_db.py` checks this. |
| Derived, computed on read | all views | nothing stored, always current |

Cash is deliberately **not** stored. `account_cash` computes it from the ledger, so it cannot drift out of sync:

```
cash = deposits + sells + dividends − withdrawals − buys − fees
```

---

## 5. The analytical layer (views)

All in `db/views/analytics_views.sql`. The API reads these instead of repeating the SQL.

| View | What it gives you | How |
|---|---|---|
| `latest_prices` | most recent close per security | `DISTINCT ON (security_id) ... ORDER BY price_date DESC`. Uses the latest available price because today's may not exist (weekends, holidays). |
| `account_positions` | per account and security: quantity, avg cost, current price, market value, cost basis, unrealized P/L | `holdings` joined to `securities` and `latest_prices` |
| `account_portfolio_value` | per account totals and return % | `account_positions` grouped by account |
| `account_cash` | cash balance per account | ledger sums minus fees |
| `daily_security_returns` | daily % return per security | `LAG(close_price)` window function |
| `daily_trading_volume` | buy and sell volume per day | `SUM(...) FILTER (WHERE ...)` grouped by date |

Definitions used by the dashboard:

- **Market value** = quantity × latest close
- **Cost basis** = quantity × average cost
- **Unrealized P/L** = market value − cost basis (profit on positions not yet sold)
- **Portfolio value** = sum of market value
- **AUM (assets under management)** = portfolio value + cash
- **Average cost** = weighted average of buy prices; sells do not change it; fees are not included

---

## 6. How the data is created (`scripts/generate_data.py`)

The generator is **seeded** (seed 42), so the same command always gives the same data. It does not just fill tables with random rows. It **replays a timeline**, so the data obeys real rules:

1. Create customers, accounts, securities, and 500 business days of prices. Prices are a random walk per security (bonds have lower volatility).
2. Create dividend events (quarterly, for ETFs, bonds, funds and about 40% of stocks).
3. Create candidate trades with random account, security, day and quantity.
4. Sort every event (trades, dividend ex-dates, dividend payments) by time and process them in order:
   - **SELL** with nothing held becomes a BUY; a SELL larger than the position is cut down to what is held.
   - **BUY** with not enough cash first inserts a DEPOSIT, then buys. Cash never goes negative.
   - Each trade updates the position and weighted average cost, writes a transaction, an order, and fees (0.05% commission; a small regulatory fee on sells).
   - Some extra orders are CANCELLED or REJECTED and never trade.
   - At each **ex-date** the generator snapshots who holds the security; on the **payment date** it pays those holders `quantity × dividend_per_share`.
5. The final positions become the `holdings` table.

Scales:

| Scale | Customers | Accounts | Securities | Trades |
|---|---|---|---|---|
| `small` | 100 | 200 | 50 | 1,000 |
| `full` | 10,000 | 15,000 | 2,000 | 300,000 |

Because everything is derived from one simulation, the two checks in `setup_db.py` pass: no account has negative cash, and holdings equal buys minus sells.

---

## 7. How the data gets into Neon (`scripts/setup_db.py`)

1. Reads `DATABASE_URL` from `.env`.
2. `DROP TABLE ... CASCADE` for all tables, then runs `01_tables.sql`. Re-running gives a clean slate.
3. For each CSV, in foreign-key order, uses PostgreSQL `COPY ... FROM STDIN`. `COPY` streams the file and is far faster than row-by-row `INSERT`.
4. Resets each identity sequence with `setval`. The CSVs carry explicit ids, so without this the next normal `INSERT` would try to reuse id 1. (The ids are `GENERATED BY DEFAULT`, which allows explicit values.)
5. Creates the views and `execute_trade()`.
6. Runs `ANALYZE` so the query planner has fresh statistics.
7. Runs the two consistency checks and prints the result.

---

## 8. How the data is stored in Neon

### 8.1 What Neon is

Neon is **standard PostgreSQL** run as a managed, serverless service. Everything in this project (SQL, constraints, views, plpgsql, `COPY`, `EXPLAIN`) is ordinary Postgres and would run unchanged on RDS, Cloud SQL or a self-hosted server.

What Neon changes is the infrastructure:

| Aspect | What it means |
|---|---|
| Compute and storage are separate | The Postgres process (compute) can start, stop and resize independently of where the data lives. |
| Scale to zero | Idle compute suspends after a period of inactivity; the first query afterwards takes a moment to wake it. That is why a first connection can be slow, and why the API pool validates connections before use. |
| Branching | You can create a copy-on-write branch of the database, useful for testing a migration without touching real data. |
| Point-in-time restore | Because the storage layer keeps the write-ahead log history, you can restore to an earlier moment within your plan's retention window. |
| Connection pooling | Neon offers a pooled endpoint for many short-lived connections. This project uses a small pool inside the API instead. |

### 8.2 How a row is stored

Inside PostgreSQL (and therefore Neon):

- Each table is stored as a set of **8 KB pages**; each page holds many rows.
- A **primary key or index** is a separate B-tree structure that maps key values to row locations. Without an index on `account_id`, finding one account's transactions means reading every page (a sequential scan). With the composite index, Postgres jumps straight to the right place.
- Every change is first written to the **write-ahead log (WAL)**, which is what makes commits durable and transactions recoverable.
- **MVCC**: updates create new row versions, so readers are not blocked by writers. That is why dashboards can read while trades are being posted.
- `NUMERIC(18,4)` stores exact decimal digits, so `0.1 + 0.2` is exactly `0.3`.

### 8.3 How this project connects

```
postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/investment_db?sslmode=require
             └ role ┘└ secret ┘└──────────── host ─────────────────┘└─ database ─┘└─ TLS ─┘
```

- The string lives only in `.env`, which is git-ignored. The repo contains `.env.example` with a placeholder.
- `sslmode=require` encrypts traffic between your machine and Neon.
- `setup_db.py` and `benchmark_indexes.py` open a direct connection. The API keeps a pool of 1 to 5 connections and validates each before use (`check=ConnectionPool.check_connection`) so a connection killed during a suspend is replaced instead of failing the request.

---

## 9. Runtime data flow, step by step

Example: you open the **Portfolio** page and pick account 143.

```
1. Portfolio.jsx          useApi("/portfolio/143")                       frontend/src/pages/Portfolio.jsx
2. api.js                 fetch("/api/portfolio/143")                    frontend/src/api.js
3. Vite dev proxy         forwards /api/* to http://localhost:8000       frontend/vite.config.js
4. FastAPI                portfolio(account_id=143)                      backend/main.py
5. SQL query 1            account + customer + cash (account_cash view)
6. SQL query 2            positions  ← account_positions view
7. SQL query 3            totals (sum of market value, cost, P/L)
8. psycopg                parameters are BOUND (%(id)s), never string-joined
9. Neon                   runs the queries, returns rows
10. FastAPI               returns JSON (404 if the account does not exist)
11. Portfolio.jsx         renders stat cards and the holdings table
```

Each page works the same way:

| Page | Endpoint(s) | Database objects used |
|---|---|---|
| Dashboard | `GET /api/summary` | `account_portfolio_value`, `account_cash`, `transactions`, `fees` |
| Portfolio | `GET /api/accounts`, `GET /api/portfolio/{id}` | `account_portfolio_value`, `account_positions`, `account_cash` |
| Transactions | `GET /api/securities`, `GET /api/transactions` | `transactions`, `securities` |
| Analytics | `GET /api/analytics/top-customers`, `most-traded`, `daily-volume`, `performance`, `returns/{id}`, `fees`, `dividends` | `daily_trading_volume`, `daily_security_returns`, `account_portfolio_value`, `fees`, `transactions` |

The transactions endpoint builds its `WHERE` clause from only the filters the user set. Every value goes in as a bound parameter, and `transaction_type` is also validated by a regex, so there is no SQL injection path.

---

## 10. Writing data safely: `execute_trade()`

File: `db/functions/portfolio_functions.sql`. Demo: `db/queries/04_trade_transaction.sql`.

Posting one trade must change three tables together:

```
transactions  ← INSERT the trade
holdings      ← INSERT or UPDATE the position (recompute weighted average cost on BUY)
fees          ← INSERT the commission
```

If the second step failed after the first succeeded, the books would be wrong. The function guarantees **all or nothing**:

- A PostgreSQL function body runs inside the caller's transaction. Any `RAISE EXCEPTION` aborts and rolls back everything.
- **BUY** first checks `account_cash` for enough money.
- **SELL** locks the holdings row (`SELECT ... FOR UPDATE`) and checks enough shares are held. The lock stops two simultaneous sells from both passing the check.
- Average cost on a BUY: `(old_qty × old_avg + new_qty × price) / (old_qty + new_qty)`.
- A SELL that empties the position deletes the holdings row.

The web UI does not call this function; the dashboard is read-only. The function exists to show how writes are done correctly.

---

## 11. Performance work (`scripts/benchmark_indexes.py`)

Question: *"Show one account's transactions after a date"*, which is exactly what the Transactions page does.

```sql
SELECT * FROM transactions WHERE account_id = X AND transaction_date >= DATE 'D';
```

The script:

1. Drops `idx_transactions_account_date` if it exists and runs `ANALYZE`.
2. Runs `EXPLAIN (ANALYZE)` 7 times and records the median execution time and plan node types (expect a sequential scan).
3. Creates the index `(account_id, transaction_date)` from `02_indexes.sql` and runs `ANALYZE`.
4. Measures again (expect an index or bitmap scan).
5. Writes both numbers and both full plans to `docs/query-optimization.md`.

Why this column order: equality on `account_id` first, range on `transaction_date` second, so one index lookup narrows to the account and then to the date range.

Notes for the interview:

- The numbers are produced from your own database; nothing is typed in by hand.
- On tiny data Postgres may keep a sequential scan because it is cheaper than an index. The benefit shows on the full dataset.
- Indexes speed reads but cost write time and storage, which is why only one was added.

---

## 12. The frontend

| File | Role |
|---|---|
| `App.jsx` | Sidebar and page switch. Uses the URL hash (`#portfolio`), so no routing library is needed. |
| `api.js` | `useApi(path, params)` returns `{data, error, loading}` and refetches when inputs change. Requests are debounced and cancelled when filters change. Also the money, number and percent formatters. |
| `ui.jsx` | `Panel`, `Stat`, `DataTable`, `Async` (loading/error wrapper), chart styling. |
| `pages/*.jsx` | One file per screen. Each declares its data needs and renders. |
| `styles.css` | Pixel theme: Press Start 2P for labels, VT323 for data, square corners, hard offset shadows, stepped chart lines, a 40-block buy/sell meter. |

State is local (`useState`) and there is no global store, because no data is shared between pages.

The Transactions page filters by account ID through `GET /api/transactions?account_id=...`.
The endpoint returns the filtered page and total in one SQL round trip, which keeps account
search and pagination responsive on the full dataset.

---

## 13. How a real company would do this

This project is a **single-database, single-user simplification**. A production system is organized around the same ideas but separates concerns more.

### 13.1 Where the data really comes from

Real firms do not generate data. They receive it:

| Data | Typical source |
|---|---|
| Customers, accounts | CRM / account-opening systems |
| Orders | Order management system (OMS) |
| Executions, positions, cash | Custodian or clearing firm, trading engine |
| Prices, corporate actions | Market data vendors (Bloomberg, Refinitiv, ICE and similar) |

These arrive as files, message queues or change feeds, and are loaded by an **ingestion pipeline** (batch ETL on a schedule, or streaming/CDC for near-real-time). Your `generate_data.py` plus `setup_db.py` is a stand-in for that pipeline: produce data, validate it, load it.

### 13.2 Separate systems for separate jobs

```
 Source systems ──▶ ingestion / ETL ──▶ ┌──────────────────────┐
 (OMS, custodian,                       │ OLTP database         │ ← writes: trades, orders
  market data)                          │ (PostgreSQL)          │
                                        └─────────┬────────────┘
                                                  │ replication
                              ┌───────────────────┼───────────────────┐
                              ▼                   ▼                   ▼
                      read replica          data warehouse        audit / archive
                      (dashboards, API)   (Snowflake, BigQuery)   (immutable storage)
                                          heavy analytics, BI
```

- **OLTP database**: many small, correct writes. Constraints, transactions and locking matter most. This is the part this project models.
- **Read replica**: serves dashboards and APIs so reporting never slows trading.
- **Data warehouse**: large, slow analytical queries over years of history.
- Heavy analytics against the live trading database is exactly what real firms avoid.

### 13.3 Who can access what

In this project one connection string can do everything. In a company, access is layered:

| Layer | Practice |
|---|---|
| Database roles | Separate roles per purpose, least privilege. The API gets read-only access to **views only**, not raw tables. |
| Authentication | Users sign in through company SSO; the API checks who they are on every request. |
| Authorization | An advisor sees only their own clients. PostgreSQL supports this with **row-level security**. |
| Network | The database is not on the public internet. Access goes through a private network or an allow-list, with TLS. |
| Secrets | Passwords live in a secrets manager (not `.env` files) and are rotated. |
| Auditing | Every access and change is logged; financial records are kept immutable for the retention period. |
| Browser | Never connects to the database. Only the API does. (This project follows that rule.) |

Example of the read-only role a real deployment would use for the API:

```sql
CREATE ROLE analytics_api LOGIN PASSWORD '...';          -- password comes from a secrets manager
GRANT USAGE ON SCHEMA public TO analytics_api;
GRANT SELECT ON account_positions, account_portfolio_value, account_cash,
                daily_security_returns, daily_trading_volume, latest_prices
      TO analytics_api;
-- plus SELECT on the few tables the API queries directly; no INSERT / UPDATE / DELETE anywhere
```

Row-level security example (advisor sees only assigned clients):

```sql
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY advisor_sees_own ON accounts
    USING (advisor_id = current_setting('app.advisor_id')::bigint);
```
(`advisor_id` does not exist in this project's schema; it is shown only to illustrate the technique.)

### 13.4 Operating it

| Concern | Real-world practice |
|---|---|
| Schema changes | Versioned migrations (Flyway, Alembic, Liquibase) run by CI, not hand-run SQL files |
| Backups and recovery | Automated backups plus point-in-time restore; recovery drills |
| Monitoring | Slow-query logging, connection and lock monitoring, alerting |
| Data quality | Reconciliation jobs comparing positions with the custodian's records. `setup_db.py` checks are a miniature version. |
| Testing | A staging database (on Neon, a **branch**) for trying migrations before production |
| Scale | Partitioning large tables like `transactions` by date, archiving old data |
| Money and compliance | Exact decimals (`NUMERIC`), immutable ledgers (corrections are new reversing entries, not edits), retention rules set by regulators |

---

## 14. What this project simplifies (be upfront about it)

- Data is synthetic; prices are a random walk.
- One currency; no taxes, margin, settlement delay, splits or other corporate actions.
- `holdings` is a stored copy of what the ledger implies. Real systems often derive positions from the ledger or reconcile continuously with a custodian.
- The API has no authentication and connects with a single privileged connection string.
- The dashboard is read-only; `execute_trade()` is not exposed.
- Average cost excludes fees; there is no tax-lot accounting (FIFO, specific lot).
- Dividends are paid on the ex-date holding with no withholding.

---

## 15. Quick reference

```bash
# one-time setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then paste the Neon connection string

# build the database
python scripts/generate_data.py --scale small      # or --scale full
python scripts/setup_db.py                         # both checks must print 0
python scripts/benchmark_indexes.py                # writes docs/query-optimization.md

# run the app
cd backend  && uvicorn main:app --reload           # http://localhost:8000/docs
cd frontend && npm install && npm run dev          # http://localhost:5173
```

### Likely interview questions this guide prepares you for

| Question | Where to look |
|---|---|
| Why NUMERIC and not FLOAT? | §4.3 |
| Why is `holdings` derived, and how do you know it is right? | §4.4, §7 |
| Why compute cash instead of storing it? | §4.4 |
| Why use the latest price instead of today's? | §5 |
| How do you keep a trade consistent across three tables? | §10 |
| How did you decide on the index and prove it helped? | §11 |
| What happens if two sells hit the same position at once? | §10 (`FOR UPDATE`) |
| How would this run in production? | §13 |
| What would you change first? | §14, then §13.3 (read-only role, auth) |