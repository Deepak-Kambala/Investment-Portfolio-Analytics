-- Applied by scripts/benchmark_indexes.py AFTER measuring the query without it.
-- Serves: "transactions for an account in a date range" (API transactions page, per-account queries).
CREATE INDEX IF NOT EXISTS idx_transactions_account_date
    ON transactions (account_id, transaction_date);
