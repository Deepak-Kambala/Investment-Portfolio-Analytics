-- execute_trade: one trade = transaction row + holdings change + fee row.
-- A plpgsql function body runs inside the caller's transaction, so if any step raises,
-- everything rolls back together.
CREATE OR REPLACE FUNCTION execute_trade(
    p_account_id  BIGINT,
    p_security_id BIGINT,
    p_side        TEXT,
    p_quantity    NUMERIC,
    p_price       NUMERIC,
    p_fee_rate    NUMERIC DEFAULT 0.0005
) RETURNS BIGINT
LANGUAGE plpgsql AS $$
DECLARE
    v_amount NUMERIC(20,4) := ROUND(p_quantity * p_price, 4);
    v_fee    NUMERIC(18,4) := ROUND(p_quantity * p_price * p_fee_rate, 4);
    v_held   NUMERIC;
    v_cash   NUMERIC;
    v_txn_id BIGINT;
BEGIN
    IF p_side NOT IN ('BUY', 'SELL') THEN
        RAISE EXCEPTION 'invalid side: %', p_side;
    END IF;

    IF p_side = 'BUY' THEN
        SELECT cash_balance INTO v_cash FROM account_cash WHERE account_id = p_account_id;
        IF COALESCE(v_cash, 0) < v_amount + v_fee THEN
            RAISE EXCEPTION 'insufficient cash: have %, need %', COALESCE(v_cash, 0), v_amount + v_fee;
        END IF;
    ELSE
        -- lock the row so two concurrent sells cannot both pass the check
        SELECT quantity INTO v_held FROM holdings
        WHERE account_id = p_account_id AND security_id = p_security_id FOR UPDATE;
        IF COALESCE(v_held, 0) < p_quantity THEN
            RAISE EXCEPTION 'insufficient holdings: have %, need %', COALESCE(v_held, 0), p_quantity;
        END IF;
    END IF;

    INSERT INTO transactions (account_id, security_id, transaction_type, quantity, price, amount, transaction_date)
    VALUES (p_account_id, p_security_id, p_side, p_quantity, p_price, v_amount, CURRENT_TIMESTAMP)
    RETURNING transaction_id INTO v_txn_id;

    IF p_side = 'BUY' THEN
        INSERT INTO holdings (account_id, security_id, quantity, average_cost)
        VALUES (p_account_id, p_security_id, p_quantity, p_price)
        ON CONFLICT (account_id, security_id) DO UPDATE
        SET average_cost = ROUND((holdings.quantity * holdings.average_cost + EXCLUDED.quantity * EXCLUDED.average_cost)
                                 / (holdings.quantity + EXCLUDED.quantity), 4),
            quantity     = holdings.quantity + EXCLUDED.quantity,
            updated_at   = CURRENT_TIMESTAMP;
    ELSE
        UPDATE holdings SET quantity = quantity - p_quantity, updated_at = CURRENT_TIMESTAMP
        WHERE account_id = p_account_id AND security_id = p_security_id;
        DELETE FROM holdings WHERE account_id = p_account_id AND security_id = p_security_id AND quantity = 0;
    END IF;

    INSERT INTO fees (transaction_id, fee_type, amount) VALUES (v_txn_id, 'COMMISSION', v_fee);
    RETURN v_txn_id;
END;
$$;
