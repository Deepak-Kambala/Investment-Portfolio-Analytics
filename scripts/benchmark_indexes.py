"""Measure one query before and after the composite index; writes docs/query-optimization.md.

    python scripts/benchmark_indexes.py
Numbers come from EXPLAIN ANALYZE on your own database, nothing is hard-coded.
"""
import os
import statistics
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
RUNS = 7


def node_types(plan):
    yield plan["Node Type"]
    for child in plan.get("Plans", []):
        yield from node_types(child)


def measure(conn, query):
    times, plan = [], None
    for _ in range(RUNS):
        plan = conn.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + query).fetchone()[0][0]
        times.append(plan["Execution Time"])
    text = "\n".join(r[0] for r in conn.execute("EXPLAIN (ANALYZE, BUFFERS) " + query))
    return statistics.median(times), " > ".join(dict.fromkeys(node_types(plan["Plan"]))), text


def main():
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        account = conn.execute("SELECT account_id FROM transactions GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
        lo, hi = conn.execute("SELECT MIN(transaction_date), MAX(transaction_date) FROM transactions").fetchone()
        since = (lo + (hi - lo) / 2).date()
        total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        query = f"SELECT * FROM transactions WHERE account_id = {account} AND transaction_date >= DATE '{since}'"

        conn.execute("DROP INDEX IF EXISTS idx_transactions_account_date")
        conn.execute("ANALYZE transactions")
        before = measure(conn, query)
        conn.execute((ROOT / "db/schema/02_indexes.sql").read_text())
        conn.execute("ANALYZE transactions")
        after = measure(conn, query)

    md = f"""# Query optimization

Table `transactions`: {total:,} rows. Times are the median of {RUNS} `EXPLAIN ANALYZE` runs on Neon.

```sql
{query}
```

| | Plan nodes | Execution time (ms) |
|---|---|---|
| Before (no index on account_id) | {before[1]} | {before[0]:.3f} |
| After `idx_transactions_account_date (account_id, transaction_date)` | {after[1]} | {after[0]:.3f} |

Why the composite index: equality on `account_id` first, then a range on `transaction_date`,
so a single index lookup narrows to the account and then to the date range, instead of reading the whole table.

## Plan before
```
{before[2]}
```

## Plan after
```
{after[2]}
```
"""
    (ROOT / "docs" / "query-optimization.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
