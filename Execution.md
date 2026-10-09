# Execution guide

Every command needed to set up, run, verify and maintain the project, with the purpose of each.
Run all commands from the project root (`investment-portfolio-analytics/`) unless a `cd` is shown.

## Order at a glance

```
1 Setup  →  2 Build database  →  3 Verify  →  4 Benchmark  →  5 Run app  →  6 Commit
```

---

## 1. One-time setup

| Command | Purpose |
|---|---|
| `python -m venv .venv` | Creates an isolated Python environment so project packages do not touch your system Python. |
| `source .venv/bin/activate` | Activates it (Windows: `.venv\Scripts\activate`). Do this in every new terminal. |
| `pip install -r requirements.txt` | Installs faker, numpy, pandas, psycopg, psycopg_pool, python-dotenv, fastapi, uvicorn. |
| `cp .env.example .env` | Creates your private config file (Windows: `copy .env.example .env`). |
| *edit `.env`* | Set `DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/investment_db?sslmode=require` (Neon console → Connect). `.env` is git-ignored, so the password never reaches GitHub. |

---

## 2. Build the database

| Command | Purpose |
|---|---|
| `python scripts/generate_data.py --scale small` | Simulates customers, accounts, securities, 500 days of prices, trades, dividends and fees, and writes 9 CSV files into `data/`. `small` is about 3.4k transactions, for development. |
| `python scripts/generate_data.py --scale full` | Same, at full size (10k customers, 15k accounts, 2k securities, about 300k trades). Use for the final benchmark and screenshots. Needs more Neon storage. |
| `python scripts/setup_db.py` | Connects to Neon, drops and recreates the tables, bulk-loads the CSVs with `COPY`, resets id sequences, creates the views and `execute_trade()`, runs `ANALYZE`, then runs the consistency checks. Safe to re-run: it rebuilds from scratch. |

Expected end of `setup_db.py` output:

```
check: accounts with negative cash (expect 0): 0
check: holdings that do not equal buys - sells (expect 0): 0
```

Both must be `0`. Anything else means the data is inconsistent.

**Changing data size:** run `generate_data.py` with the new scale, then `setup_db.py` again.

---

## 3. Verify and explore the SQL (optional, needs `psql`)

Install the client if missing: `brew install libpq` (Mac) or use the VS Code PostgreSQL extension instead.

| Command | Purpose |
|---|---|
| `set -a; source .env; set +a` | Loads `DATABASE_URL` into your shell so `psql` can use it. |
| `psql "$DATABASE_URL" -c "SELECT version();"` | Confirms the connection to Neon works. |
| `psql "$DATABASE_URL" -c "\dt"` | Lists the 9 tables. |
| `psql "$DATABASE_URL" -c "\dv"` | Lists the 6 views. |
| `psql "$DATABASE_URL" -f db/queries/01_basic.sql` | Runs aggregates, joins, an anti-join and a subquery. |
| `psql "$DATABASE_URL" -f db/queries/02_ctes.sql` | Runs the CTE queries: portfolio value per account and sector exposure. |
| `psql "$DATABASE_URL" -f db/queries/03_window_functions.sql` | Runs running totals, `LAG` daily returns and `RANK`. |
| `psql "$DATABASE_URL" -f db/queries/04_trade_transaction.sql` | Demonstrates an atomic trade with `execute_trade()`. The last `SELL` is meant to fail with "insufficient holdings", and the script ends with `ROLLBACK`, so no data changes. |

Running these files by hand is also good interview preparation: be ready to explain what each one returns.

---

## 4. Benchmark the index

| Command | Purpose |
|---|---|
| `python scripts/benchmark_indexes.py` | Drops the index `idx_transactions_account_date`, measures one query with `EXPLAIN ANALYZE` (median of 7 runs), creates the index, measures again, and writes both plans and timings to `docs/query-optimization.md`. |

- Run it on **full-scale** data. On tiny data Postgres may keep using a sequential scan, which is correct behaviour.
- Never edit the generated numbers. Re-run the script if you reload data.
- Leaves the index in place afterwards, so the app runs with it.

---

## 5. Run the application

Use two terminals. Activate the venv in the first.

| Terminal | Command | Purpose |
|---|---|---|
| 1 | `cd backend` | Moves into the API folder. |
| 1 | `uvicorn main:app --reload` | Starts FastAPI on http://localhost:8000. `--reload` restarts it when code changes. |
| 2 | `cd frontend` | Moves into the UI folder. |
| 2 | `npm install` | Installs React, Recharts and Vite (first time only). |
| 2 | `npm run dev` | Starts the UI on http://localhost:5173 and proxies `/api` calls to port 8000. |

Useful URLs:

| URL | What it is |
|---|---|
| http://localhost:5173 | The dashboard |
| http://localhost:8000/docs | Interactive API documentation (try each endpoint) |
| http://localhost:8000/api/summary | Raw JSON behind the dashboard |

Stop either server with `Ctrl+C`.

Optional production build of the UI: `cd frontend && npm run build` creates `frontend/dist/`, a static bundle. Not needed for the interview.

---

## 6. Commit and push

| Command | Purpose |
|---|---|
| `git status` | Shows what changed. Confirm `.env` and `data/*.csv` are **not** listed. |
| `git add .` | Stages all changes (the `.gitignore` keeps secrets and generated data out). |
| `git commit -m "Add benchmark results and docs"` | Records the change locally. |
| `git push` | Uploads it to GitHub. |

Files worth committing after the full run: `docs/query-optimization.md`, `docs/PROJECT_GUIDE.md`, `docs/EXECUTION.md`, and screenshots in `docs/screenshots/`.

---

## 7. Reset and troubleshooting

| Situation | What to run | Purpose |
|---|---|---|
| Start the data over | `python scripts/generate_data.py --scale small && python scripts/setup_db.py` | Regenerates and reloads everything. |
| Same data again | The same commands | The generator is seeded, so the output is identical. |
| `KeyError: 'DATABASE_URL'` | Check `.env` is in the project root and the name is exactly `DATABASE_URL` | The scripts read it from there. |
| Connection or SSL error | Make sure the string ends with `?sslmode=require` and has no quotes or spaces | Neon requires TLS. |
| First connection is slow or times out | Run the command again | Neon suspends idle compute and needs a moment to wake. |
| `uvicorn: command not found` | `source .venv/bin/activate` | The venv is not active in this terminal. |
| UI shows an error panel | Check terminal 1 is running and `http://localhost:8000/api/summary` returns JSON | The UI depends on the API. |
| Out of Neon storage | Lower `trades` under `SCALES["small"]` or use `--scale small` | Smaller dataset. |
| Port already in use | Stop the old process, or use `uvicorn main:app --port 8001` (then update `vite.config.js`) | Only one process per port. |

---

## 8. Full run, copy and paste

```bash
# setup (once)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # then paste the Neon connection string into .env

# build + verify + benchmark
python scripts/generate_data.py --scale small
python scripts/setup_db.py       # both checks must print 0
python scripts/generate_data.py --scale full
python scripts/setup_db.py
python scripts/benchmark_indexes.py

# run (two terminals)
cd backend  && uvicorn main:app --reload
cd frontend && npm install && npm run dev
```