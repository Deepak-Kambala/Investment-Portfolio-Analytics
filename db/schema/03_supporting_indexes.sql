CREATE INDEX IF NOT EXISTS idx_fees_transaction_id ON fees (transaction_id);
CREATE INDEX IF NOT EXISTS idx_transactions_security_id ON transactions (security_id);
