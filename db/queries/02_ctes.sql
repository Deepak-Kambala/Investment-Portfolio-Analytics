-- Portfolio value per account using the latest available price (not "today's", which may not exist)
WITH latest_prices AS (
    SELECT DISTINCT ON (security_id) security_id, close_price
    FROM market_prices
    ORDER BY security_id, price_date DESC
),
portfolio_values AS (
    SELECT h.account_id, SUM(h.quantity * lp.close_price) AS portfolio_value
    FROM holdings h
    JOIN latest_prices lp ON lp.security_id = h.security_id
    GROUP BY h.account_id
)
SELECT * FROM portfolio_values ORDER BY portfolio_value DESC LIMIT 10;

-- Sector exposure across all accounts
WITH exposure AS (
    SELECT s.sector, SUM(p.market_value) AS value
    FROM account_positions p
    JOIN securities s ON s.security_id = p.security_id
    WHERE s.sector IS NOT NULL
    GROUP BY s.sector
)
SELECT sector, value, ROUND(100 * value / SUM(value) OVER (), 2) AS pct_of_total
FROM exposure
ORDER BY value DESC;
