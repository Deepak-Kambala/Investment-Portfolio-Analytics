-- Running transaction value per account
SELECT account_id, transaction_date, amount,
       SUM(amount) OVER (PARTITION BY account_id ORDER BY transaction_date) AS cumulative_value
FROM transactions
WHERE transaction_type IN ('BUY', 'SELL') AND account_id = 1
ORDER BY transaction_date;

-- Daily returns with LAG (also available as the daily_security_returns view)
SELECT security_id, price_date, close_price,
       LAG(close_price) OVER w AS previous_close,
       ROUND(100 * (close_price / LAG(close_price) OVER w - 1), 4) AS daily_return_pct
FROM market_prices
WHERE security_id = 1
WINDOW w AS (PARTITION BY security_id ORDER BY price_date)
ORDER BY price_date DESC
LIMIT 20;

-- Rank securities by trading volume inside each asset type
SELECT asset_type, symbol, volume,
       RANK() OVER (PARTITION BY asset_type ORDER BY volume DESC) AS rank_in_type
FROM (
    SELECT s.asset_type, s.symbol, SUM(t.amount) AS volume
    FROM transactions t JOIN securities s ON s.security_id = t.security_id
    WHERE t.transaction_type IN ('BUY', 'SELL')
    GROUP BY s.asset_type, s.symbol
) x
ORDER BY asset_type, rank_in_type
LIMIT 20;
