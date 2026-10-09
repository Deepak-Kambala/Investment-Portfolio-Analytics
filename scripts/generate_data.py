"""Synthetic data generator. Seeded, so the same command always produces the same CSVs.

    python scripts/generate_data.py --scale small   # ~1k trades, for development
    python scripts/generate_data.py --scale full    # 10k customers, 15k accounts, 2k securities, ~300k trades

The simulation runs in time order, so the data is internally consistent:
  - a SELL never exceeds the shares held at that moment
  - a BUY never overdraws cash (a DEPOSIT is inserted first when needed)
  - holdings (quantity, weighted average cost) are the result of replaying the trades
  - a DIVIDEND is paid on the shares held on the ex-date
"""
import argparse
import string
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

SCALES = {
    "small": dict(customers=100, accounts=200, securities=50, trades=1_000),
    "full": dict(customers=10_000, accounts=15_000, securities=2_000, trades=300_000),
}
DAYS = 500  # business days of price history
SECTORS = ["Technology", "Healthcare", "Financials", "Energy", "Consumer", "Industrials", "Utilities"]
OUT = Path(__file__).resolve().parents[1] / "data"


def build(scale: str, seed: int = 42):
    cfg = SCALES[scale]
    rng = np.random.default_rng(seed)
    Faker.seed(seed)
    fake = Faker()

    days = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.offsets.BDay(1), periods=DAYS)

    # ---- customers & accounts
    n_c, n_a, n_s = cfg["customers"], cfg["accounts"], cfg["securities"]
    customers = pd.DataFrame({
        "customer_id": range(1, n_c + 1),
        "full_name": [fake.name() for _ in range(n_c)],
        "email": [f"customer{i}@example.com" for i in range(1, n_c + 1)],
        "risk_profile": rng.choice(["LOW", "MEDIUM", "HIGH"], n_c, p=[.25, .5, .25]),
        "created_at": [days[0] - timedelta(days=int(d)) for d in rng.integers(1, 700, n_c)],
    })
    opened_idx = rng.integers(0, DAYS // 3, n_a)
    accounts = pd.DataFrame({
        "account_id": range(1, n_a + 1),
        # every customer gets at least one account, the rest are spread randomly
        "customer_id": np.concatenate([np.arange(1, n_c + 1), rng.integers(1, n_c + 1, n_a - n_c)]),
        "account_type": rng.choice(["BROKERAGE", "RETIREMENT", "CASH"], n_a, p=[.6, .3, .1]),
        "status": rng.choice(["ACTIVE", "CLOSED"], n_a, p=[.97, .03]),
        "opened_at": [days[i].date() for i in opened_idx],
    })

    # ---- securities
    symbols = set()
    while len(symbols) < n_s:
        symbols.add("".join(rng.choice(list(string.ascii_uppercase), int(rng.integers(3, 5)))))
    asset_type = rng.choice(["STOCK", "ETF", "BOND", "MUTUAL_FUND"], n_s, p=[.6, .2, .1, .1])
    securities = pd.DataFrame({
        "security_id": range(1, n_s + 1),
        "symbol": sorted(symbols),
        "security_name": [fake.company() for _ in range(n_s)],
        "asset_type": asset_type,
        "sector": [rng.choice(SECTORS) if t == "STOCK" else None for t in asset_type],
    })

    # ---- market prices: geometric random walk per security
    sigma = np.where(asset_type == "BOND", 0.003, rng.uniform(0.01, 0.03, n_s))
    start = np.where(asset_type == "BOND", rng.uniform(90, 110, n_s), rng.lognormal(4, .7, n_s))
    ret = rng.normal(0.0003, sigma[:, None], (n_s, DAYS))
    close = np.round(start[:, None] * np.exp(np.cumsum(ret, axis=1)), 2)
    prev = np.concatenate([start[:, None], close[:, :-1]], axis=1)
    open_ = np.round(prev * (1 + rng.normal(0, .002, (n_s, DAYS))), 2)
    high = np.round(np.maximum(open_, close) * (1 + np.abs(rng.normal(0, .004, (n_s, DAYS)))), 2)
    low = np.round(np.minimum(open_, close) * (1 - np.abs(rng.normal(0, .004, (n_s, DAYS)))), 2)
    market_prices = pd.DataFrame({
        "security_id": np.repeat(np.arange(1, n_s + 1), DAYS),
        "price_date": np.tile([d.date() for d in days], n_s),
        "open_price": open_.ravel(), "high_price": high.ravel(),
        "low_price": low.ravel(), "close_price": close.ravel(),
        "volume": rng.integers(50_000, 5_000_000, n_s * DAYS),
    })

    # ---- dividends: quarterly for ETFs/bonds/funds and ~40% of stocks
    payer = (asset_type != "STOCK") | (rng.random(n_s) < .4)
    dividends, events = [], []
    for s in np.flatnonzero(payer):
        for d in range(int(rng.integers(5, 60)), DAYS - 12, 63):
            pay = days[d] + timedelta(days=14)
            if pay > days[-1]:
                continue
            dividends.append((int(s) + 1, days[d].date(), pay.date(), round(float(close[s, d] * rng.uniform(.002, .008)), 4)))
    dividends = pd.DataFrame(dividends, columns=["security_id", "ex_date", "payment_date", "dividend_per_share"])
    dividends.insert(0, "dividend_id", range(1, len(dividends) + 1))
    for r in dividends.itertuples():
        events.append((pd.Timestamp(r.ex_date), 1, ("EX", r)))
        events.append((pd.Timestamp(r.payment_date) + timedelta(hours=9), 2, ("PAY", r)))

    # ---- trade events (candidate trades; the simulation may flip/shrink them to stay consistent)
    active = accounts.loc[accounts.status == "ACTIVE", "account_id"].to_numpy()
    n_t = cfg["trades"]
    acct = rng.choice(active, n_t)
    day = np.array([rng.integers(opened_idx[a - 1], DAYS) for a in acct])
    secs = rng.integers(0, n_s, n_t)
    for i in range(n_t):
        ts = days[day[i]] + timedelta(seconds=int(rng.integers(9 * 3600 + 1800, 16 * 3600)))
        events.append((ts, 0, ("T", acct[i], int(secs[i]), int(day[i]), "BUY" if rng.random() < .6 else "SELL", float(rng.integers(1, 200)))))
    events.sort(key=lambda e: (e[0], e[1]))

    # ---- simulation
    cash = {int(a): 0.0 for a in accounts.account_id}
    pos = {}                      # (account, security) -> [qty, avg_cost, last_ts]
    holders = {s: set() for s in range(1, n_s + 1)}
    snapshots = {}                # dividend_id -> [(account, qty)]
    txns, fees, orders = [], [], []

    def add_txn(a, s, typ, q, p, amt, ts):
        txns.append((len(txns) + 1, a, s, typ, q, p, round(amt, 4), ts))
        return len(txns)

    for ts, _, ev in events:
        if ev[0] == "EX":
            r = ev[1]
            snapshots[r.dividend_id] = [(a, pos[(a, r.security_id)][0]) for a in holders[r.security_id]]
        elif ev[0] == "PAY":
            r = ev[1]
            for a, q in snapshots.pop(r.dividend_id, []):
                amt = q * r.dividend_per_share
                cash[a] += round(amt, 4)
                add_txn(a, r.security_id, "DIVIDEND", q, r.dividend_per_share, amt, ts)
        else:
            _, a, s0, d, side, qty = ev
            a, s = int(a), s0 + 1
            if asset_type[s0] == "MUTUAL_FUND":
                qty = round(qty / 3, 4)
            price = float(close[s0, d])
            held = pos.get((a, s), [0, 0, None])[0]
            if side == "SELL" and held <= 0:
                side = "BUY"
            if side == "SELL":
                qty = min(qty, held)
            amount = round(qty * price, 4)
            commission = round(amount * 0.0005, 4)
            sec_fee = round(amount * 0.000008, 4) if side == "SELL" else 0.0
            order_type = "LIMIT" if rng.random() < .35 else "MARKET"
            submitted = ts - timedelta(seconds=int(rng.integers(1, 60)))
            if rng.random() < .1:  # an order that never traded
                orders.append((len(orders) + 1, a, s, side, qty, order_type, rng.choice(["CANCELLED", "REJECTED"]), submitted - timedelta(seconds=5)))
            if side == "BUY":
                need = amount + commission
                if cash[a] < need:
                    top = round(need - cash[a] + float(rng.uniform(1_000, 20_000)), 2)
                    add_txn(a, None, "DEPOSIT", None, None, top, ts - timedelta(seconds=1))
                    cash[a] += top
                cash[a] -= need
                q0, c0, _ = pos.get((a, s), [0, 0, None])
                pos[(a, s)] = [round(q0 + qty, 4), round((q0 * c0 + qty * price) / (q0 + qty), 4), ts]
                holders[s].add(a)
            else:
                cash[a] += amount - commission - sec_fee
                pos[(a, s)][0] = round(pos[(a, s)][0] - qty, 4)
                pos[(a, s)][2] = ts
                if pos[(a, s)][0] <= 0:
                    holders[s].discard(a)
            orders.append((len(orders) + 1, a, s, side, qty, order_type, "FILLED", submitted))
            tid = add_txn(a, s, side, qty, price, amount, ts)
            fees.append((len(fees) + 1, tid, "COMMISSION", commission))
            if sec_fee:
                fees.append((len(fees) + 1, tid, "SEC_FEE", sec_fee))
            if side == "BUY" and rng.random() < .01 and cash[a] > 5_000:   # occasional withdrawal
                w = round(cash[a] * float(rng.uniform(.1, .5)), 2)
                cash[a] -= w
                add_txn(a, None, "WITHDRAWAL", None, None, w, ts + timedelta(seconds=1))

    holdings = pd.DataFrame(
        [(i + 1, a, s, q, c, t) for i, ((a, s), (q, c, t)) in enumerate((k, v) for k, v in pos.items() if v[0] > 0)],
        columns=["holding_id", "account_id", "security_id", "quantity", "average_cost", "updated_at"])

    transactions = pd.DataFrame(txns, columns=["transaction_id", "account_id", "security_id", "transaction_type", "quantity", "price", "amount", "transaction_date"])
    transactions["security_id"] = transactions["security_id"].astype("Int64")
    return {
        "customers": customers, "accounts": accounts, "securities": securities,
        "market_prices": market_prices, "dividends": dividends,
        "orders": pd.DataFrame(orders, columns=["order_id", "account_id", "security_id", "side", "quantity", "order_type", "order_status", "submitted_at"]),
        "transactions": transactions, "holdings": holdings,
        "fees": pd.DataFrame(fees, columns=["fee_id", "transaction_id", "fee_type", "amount"]),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=SCALES, default="small")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    for name, df in build(args.scale).items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:14s}{len(df):>10,} rows")
