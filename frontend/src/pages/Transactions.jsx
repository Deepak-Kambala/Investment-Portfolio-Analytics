import { useEffect, useState } from "react";
import { num, useApi, usdExact } from "../api.js";
import { Async, DataTable, Panel } from "../ui.jsx";

const TYPES = ["BUY", "SELL", "DIVIDEND", "DEPOSIT", "WITHDRAWAL"];
const LIMIT = 25;

export default function Transactions() {
  const [f, setF] = useState({ account_id: "", security_id: "", transaction_type: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(0);
  const securities = useApi("/securities");
  const t = useApi("/transactions", { ...f, limit: LIMIT, offset: page * LIMIT });
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setPage(0); };
  useEffect(() => {
    if (t.data) setPage((current) => Math.min(current, Math.max(0, Math.ceil(t.data.total / LIMIT) - 1)));
  }, [t.data?.total]);

  return (
    <>
      <Panel title="Filters">
        <div className="filters">
          <label>Account id<input type="number" min="1" value={f.account_id} onChange={set("account_id")} /></label>
          <label>Security
            <select value={f.security_id} onChange={set("security_id")}>
              <option value="">All</option>
              {securities.data?.map((s) => <option key={s.security_id} value={s.security_id}>{s.symbol}</option>)}
            </select>
          </label>
          <label>Type
            <select value={f.transaction_type} onChange={set("transaction_type")}>
              <option value="">All</option>
              {TYPES.map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>
          <label>From<input type="date" value={f.date_from} onChange={set("date_from")} /></label>
          <label>To<input type="date" value={f.date_to} onChange={set("date_to")} /></label>
        </div>
      </Panel>
      <Panel title="Transactions" aside={t.data && <span className="muted">{t.data.total.toLocaleString()} found</span>}>
        <Async state={t}>
          {(d) => (
            <>
              <DataTable
                rows={d.rows}
                columns={[
                  { key: "transaction_id", label: "Id" },
                  { key: "account_id", label: "Account" },
                  { key: "symbol", label: "Security", render: (r) => r.symbol ?? "" },
                  { key: "transaction_type", label: "Type", render: (r) => <span className={`tag ${r.transaction_type}`}>{r.transaction_type}</span> },
                  { key: "quantity", label: "Quantity", right: true, render: (r) => num(r.quantity) },
                  { key: "price", label: "Price", right: true, render: (r) => usdExact(r.price) },
                  { key: "amount", label: "Amount", right: true, render: (r) => usdExact(r.amount) },
                  { key: "transaction_date", label: "Date", render: (r) => r.transaction_date.replace("T", " ") },
                ]}
              />
              <div className="pager">
                <button disabled={t.loading || page === 0} onClick={() => setPage(page - 1)}>Prev</button>
                <span>Page {page + 1} of {Math.max(1, Math.ceil(d.total / LIMIT))}</span>
                <button disabled={t.loading || (page + 1) * LIMIT >= d.total} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </>
          )}
        </Async>
      </Panel>
    </>
  );
}
