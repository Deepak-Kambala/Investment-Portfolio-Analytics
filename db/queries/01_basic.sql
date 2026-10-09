-- Total traded volume
SELECT SUM(amount) AS total_transaction_volume
FROM transactions
WHERE transaction_type IN ('BUY', 'SELL');

-- Transactions per customer (join across 3 tables)
SELECT c.customer_id, c.full_name,
       COUNT(t.transaction_id) AS transaction_count,
       SUM(t.amount)           AS total_value
FROM customers c
JOIN accounts a     ON a.customer_id = c.customer_id
JOIN transactions t ON t.account_id  = a.account_id
WHERE t.transaction_type IN ('BUY', 'SELL')
GROUP BY c.customer_id, c.full_name
ORDER BY total_value DESC
LIMIT 10;

-- Securities that nobody holds (anti-join)
SELECT s.symbol
FROM securities s
WHERE NOT EXISTS (SELECT 1 FROM holdings h WHERE h.security_id = s.security_id);

-- Accounts whose portfolio is worth more than the average account (subquery)
SELECT account_id, market_value
FROM account_portfolio_value
WHERE market_value > (SELECT AVG(market_value) FROM account_portfolio_value)
ORDER BY market_value DESC
LIMIT 10;
