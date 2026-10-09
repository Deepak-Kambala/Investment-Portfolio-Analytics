import { useState } from "react";
import { num, pct, usd, usdExact, useApi } from "../api.js";
import { Async, DataTable, Panel, Stat, tone } from "../ui.jsx";

export default function Portfolio() {
  const accounts = useApi("/accounts");
  const [id, setId] = useState("");
  const accountId = id || accounts.data?.[0]?.account_id || "";
  const p = useApi(accountId ? `/portfolio/${accountId}` : "/accounts");

  return (
    <>
      <Panel title="Account">
        <div className="filters">
          <label>Account id
            <input type="number" min="1" value={accountId} onChange={(e) => setId(e.target.value)} />
          </label>
          <label>Top accounts by value
            <select value={accountId} onChange={(e) => setId(e.target.value)}>
              {accounts.data?.map((a) => (
                <option key={a.account_id} value={a.account_id}>#{a.account_id} {a.full_name} ({usd(a.market_value)})</option>
              ))}
            </select>
          </label>
        </div>
      </Panel>
      {accountId && p.data?.positions && (
        <>
          <p className="owner">{p.data.account.full_name}, {p.data.account.account_type.toLowerCase()} account, {p.data.account.status.toLowerCase()}</p>
          <div className="stats">
            <Stat label="Market value" value={usd(p.data.totals.market_value)} />
            <Stat label="Cost basis" value={usd(p.data.totals.cost_basis)} />
            <Stat label="Unrealized P/L" value={usd(p.data.totals.unrealized_pl)} tone={tone(p.data.totals.unrealized_pl)} />
            <Stat label="Cash" value={usd(p.data.account.cash_balance)} />
          </div>
        </>
      )}
      <Panel title="Holdings">
        {accountId && (
          <Async state={p}>
            {(d) => d.positions && (
              <DataTable
                rows={d.positions}
                empty="This account holds no securities."
                columns={[
                  { key: "symbol", label: "Security", render: (r) => <><b>{r.symbol}</b> <span className="muted">{r.security_name}</span></> },
                  { key: "quantity", label: "Quantity", right: true, render: (r) => num(r.quantity) },
                  { key: "average_cost", label: "Avg cost", right: true, render: (r) => usdExact(r.average_cost) },
                  { key: "current_price", label: "Price", right: true, render: (r) => usdExact(r.current_price) },
                  { key: "market_value", label: "Market value", right: true, render: (r) => usdExact(r.market_value) },
                  { key: "unrealized_pl", label: "Unrealized P/L", right: true, render: (r) => (
                    <span className={tone(r.unrealized_pl)}>
                      {usdExact(r.unrealized_pl)} ({pct(100 * r.unrealized_pl / r.cost_basis)})
                    </span>) },
                ]}
              />
            )}
          </Async>
        )}
      </Panel>
    </>
  );
}
