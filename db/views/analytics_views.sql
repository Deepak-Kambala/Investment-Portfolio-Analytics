-- Reusable analytical layer. The API reads these instead of repeating the SQL.

CREATE OR REPLACE VIEW latest_prices AS
SELECT DISTINCT ON (security_id) security_id, price_date, close_price
FROM market_prices
ORDER BY security_id, price_date DESC;

CREATE OR REPLACE VIEW account_positions AS
SELECT h.account_id,
       h.security_id,
       s.symbol,
       s.security_name,
       h.quantity,
       h.average_cost,
       lp.close_price                                  AS current_price,
       h.quantity * lp.close_price                     AS market_value,
       h.quantity * h.average_cost                     AS cost_basis,
       h.quantity * (lp.close_price - h.average_cost)  AS unrealized_pl
FROM holdings h
JOIN securities s    ON s.security_id  = h.security_id
JOIN latest_prices lp ON lp.security_id = h.security_id;

CREATE OR REPLACE VIEW account_portfolio_value AS
SELECT account_id,
       SUM(market_value)  AS market_value,
       SUM(cost_basis)    AS cost_basis,
       SUM(unrealized_pl) AS unrealized_pl,
       ROUND(100 * SUM(unrealized_pl) / NULLIF(SUM(cost_basis), 0), 2) AS return_pct
FROM account_positions
GROUP BY account_id;

-- Cash = money in (deposits, sells, dividends) - money out (withdrawals, buys) - fees
CREATE OR REPLACE VIEW account_cash AS
SELECT a.account_id,
       COALESCE(t.net_cash, 0) - COALESCE(f.fees, 0) AS cash_balance
FROM accounts a
LEFT JOIN (
    SELECT account_id,
           SUM(CASE WHEN transaction_type IN ('DEPOSIT', 'SELL', 'DIVIDEND') THEN amount ELSE -amount END) AS net_cash
    FROM transactions GROUP BY account_id
) t ON t.account_id = a.account_id
LEFT JOIN (
    SELECT tr.account_id, SUM(fe.amount) AS fees
    FROM fees fe JOIN transactions tr ON tr.transaction_id = fe.transaction_id
    GROUP BY tr.account_id
) f ON f.account_id = a.account_id;

CREATE OR REPLACE VIEW daily_security_returns AS
SELECT security_id,
       price_date,
       close_price,
       ROUND(100 * (close_price / LAG(close_price) OVER (PARTITION BY security_id ORDER BY price_date) - 1), 4)
           AS daily_return_pct
FROM market_prices;

CREATE OR REPLACE VIEW daily_trading_volume AS
SELECT transaction_date::date AS trade_date,
       COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'BUY'), 0)  AS buy_volume,
       COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'SELL'), 0) AS sell_volume,
       SUM(amount) AS total_volume
FROM transactions
WHERE transaction_type IN ('BUY', 'SELL')
GROUP BY transaction_date::date;
