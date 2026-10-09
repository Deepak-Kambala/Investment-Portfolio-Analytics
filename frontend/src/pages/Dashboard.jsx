import { useApi, usd } from "../api.js";
import { Async, Panel, Stat } from "../ui.jsx";

const BLOCKS = 40;

export default function Dashboard() {
  const s = useApi("/summary");
  return (
    <Async state={s}>
      {(d) => {
        const buyShare = d.total_volume ? d.buy_volume / d.total_volume : 0;
        const buyBlocks = Math.round(buyShare * BLOCKS);
        return (
          <>
            <div className="stats">
              <Stat label="Assets under management" value={usd(d.aum)} tone="hero" />
              <Stat label="Portfolio value" value={usd(d.portfolio_value)} />
              <Stat label="Cash" value={usd(d.cash)} />
              <Stat label="Accounts" value={d.accounts.toLocaleString()} />
              <Stat label="Transaction volume" value={usd(d.total_volume)} />
              <Stat label="Fees paid" value={usd(d.fees_paid)} />
              <Stat label="Dividend income" value={usd(d.dividend_income)} />
            </div>
            <Panel title="Buy vs sell volume">
              <div className="meter" role="img" aria-label={`Buys ${Math.round(buyShare * 100)} percent of volume`}>
                {Array.from({ length: BLOCKS }, (_, i) => <i key={i} className={i < buyBlocks ? "buy" : "sell"} />)}
              </div>
              <div className="meter-legend">
                <span className="gain">Buy {usd(d.buy_volume)}</span>
                <span className="loss">Sell {usd(d.sell_volume)}</span>
              </div>
            </Panel>
          </>
        );
      }}
    </Async>
  );
}
