-- One trade touches transactions, holdings and fees. Run as a unit, then roll back so the data is untouched.
BEGIN;

INSERT INTO transactions (account_id, transaction_type, amount, transaction_date)
VALUES (101, 'DEPOSIT', 10000, CURRENT_TIMESTAMP);          -- make sure the account has cash

SELECT execute_trade(101, 25, 'BUY', 10, 52.30);            -- transactions + holdings + fees, atomically

SELECT * FROM holdings WHERE account_id = 101 AND security_id = 25;

-- This raises (not enough shares) and aborts the transaction; nothing above is kept.
SELECT execute_trade(101, 25, 'SELL', 1000000, 52.30);

ROLLBACK;
