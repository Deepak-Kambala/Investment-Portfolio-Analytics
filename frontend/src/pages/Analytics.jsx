import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { compact, pct, usd, usdExact, useApi } from "../api.js";
import { Async, Chart, DataTable, Panel, axis, tone, tooltip } from "../ui.jsx";

const money = (v) => usd(v);
const grid = <CartesianGrid stroke="#b8b6af" strokeDasharray="2 4" vertical={false} />;
const yAxis = <YAxis {...axis} width={56} tickFormatter={compact} />;

function monthBars(data, color) {
  return (
    <Chart height={220}>
      <BarChart data={data}>
        {grid}
        <XAxis dataKey="month" {...axis} />
        {yAxis}
        <Tooltip {...tooltip} formatter={money} />
        <Bar dataKey="total" fill={color} isAnimationActive={false} />
      </BarChart>
    </Chart>
  );
}

function SecurityReturns() {
  const securities = useApi("/securities");
  const [id, setId] = useState("");
  const sid = id || securities.data?.[0]?.security_id;
  const r = useApi(sid ? `/analytics/returns/${sid}` : "/securities");
  return (
    <Panel
      title="Daily security returns"
      aside={
        <select value={sid ?? ""} onChange={(e) => setId(e.target.value)}>
          {securities.data?.map((s) => <option key={s.security_id} value={s.security_id}>{s.symbol}</option>)}
        </select>
      }
    >
      <Async state={r}>
        {(d) => Array.isArray(d) && d[0]?.daily_return_pct !== undefined && (
          <Chart>
            <LineChart data={d}>
              {grid}
              <XAxis dataKey="price_date" {...axis} minTickGap={48} />
              <YAxis {...axis} width={56} tickFormatter={(v) => `${v}%`} />
              <Tooltip {...tooltip} formatter={(v) => `${v}%`} />
              <Line type="stepAfter" dataKey="daily_return_pct" name="Daily return" stroke="#7c3aed" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </Chart>
        )}
      </Async>
    </Panel>
  );
}

export default function Analytics() {
  const customers = useApi("/analytics/top-customers");
  const traded = useApi("/analytics/most-traded");
  const daily = useApi("/analytics/daily-volume");
  const perf = useApi("/analytics/performance");
  const fees = useApi("/analytics/fees");
  const divs = useApi("/analytics/dividends");

  return (
    <div className="grid2">
      <Panel title="Top customers by transaction volume">
        <Async state={customers}>
          {(d) => <DataTable rows={d} columns={[
            { key: "full_name", label: "Customer" },
            { key: "trades", label: "Trades", right: true },
            { key: "volume", label: "Volume", right: true, render: (r) => usdExact(r.volume) },
          ]} />}
        </Async>
      </Panel>
      <Panel title="Most traded securities">
        <Async state={traded}>
          {(d) => (
            <Chart height={290}>
              <BarChart data={d} layout="vertical" margin={{ left: 8 }}>
                <CartesianGrid stroke="#b8b6af" strokeDasharray="2 4" horizontal={false} />
                <XAxis type="number" {...axis} />
                <YAxis type="category" dataKey="symbol" {...axis} width={64} />
                <Tooltip {...tooltip} formatter={(v, n) => (n === "Trades" ? v : money(v))} />
                <Bar dataKey="trades" name="Trades" fill="#7d8a2d" isAnimationActive={false} />
              </BarChart>
            </Chart>
          )}
        </Async>
      </Panel>
      <div className="span2">
        <Panel title="Daily transaction volume, last 90 trading days">
          <Async state={daily}>
            {(d) => (
              <Chart>
                <LineChart data={d}>
                  {grid}
                  <XAxis dataKey="trade_date" {...axis} minTickGap={48} />
                  {yAxis}
                  <Tooltip {...tooltip} formatter={money} />
                  <Line type="stepAfter" dataKey="buy_volume" name="Buy" stroke="#7d8a2d" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="stepAfter" dataKey="sell_volume" name="Sell" stroke="#b04a35" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </Chart>
            )}
          </Async>
        </Panel>
      </div>
      <Panel title="Portfolio performance: best and worst five accounts">
        <Async state={perf}>
          {(d) => <DataTable rows={d} columns={[
            { key: "account_id", label: "Account" },
            { key: "market_value", label: "Value", right: true, render: (r) => usd(r.market_value) },
            { key: "unrealized_pl", label: "Unrealized P/L", right: true, render: (r) => <span className={tone(r.unrealized_pl)}>{usd(r.unrealized_pl)}</span> },
            { key: "return_pct", label: "Return", right: true, render: (r) => <span className={tone(r.return_pct)}>{pct(r.return_pct)}</span> },
          ]} />}
        </Async>
      </Panel>
      <SecurityReturns />
      <Panel title="Fees by type">
        <Async state={fees}>
          {(d) => <DataTable rows={d.by_type} columns={[
            { key: "fee_type", label: "Fee" },
            { key: "count", label: "Count", right: true },
            { key: "total", label: "Total", right: true, render: (r) => usdExact(r.total) },
          ]} />}
        </Async>
      </Panel>
      <Panel title="Fees by month">
        <Async state={fees}>{(d) => monthBars(d.by_month, "#b04a35")}</Async>
      </Panel>
      <div className="span2">
        <Panel title="Dividend income by month">
          <Async state={divs}>{(d) => monthBars(d, "#7c3aed")}</Async>
        </Panel>
      </div>
    </div>
  );
}
