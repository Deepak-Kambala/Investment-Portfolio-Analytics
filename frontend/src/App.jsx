import { useEffect, useState } from "react";
import Dashboard from "./pages/Dashboard.jsx";
import Portfolio from "./pages/Portfolio.jsx";
import Transactions from "./pages/Transactions.jsx";
import Analytics from "./pages/Analytics.jsx";

const PAGES = { dashboard: Dashboard, portfolio: Portfolio, transactions: Transactions, analytics: Analytics };
const current = () => (location.hash.slice(1) in PAGES ? location.hash.slice(1) : "dashboard");

export default function App() {
  const [page, setPage] = useState(current);
  useEffect(() => {
    const on = () => setPage(current());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  const Page = PAGES[page];

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <svg viewBox="0 0 8 8" width="32" height="32" shapeRendering="crispEdges" aria-hidden="true">
            <path fill="#ffd25a" d="M1 5h2v2H1zM3 3h2v4H3zM5 1h2v6H5z" />
          </svg>
          <span>Portfolio<br />ledger</span>
        </div>
        <nav>
          {Object.keys(PAGES).map((p) => (
            <a key={p} href={`#${p}`} className={p === page ? "on" : ""}>{p}</a>
          ))}
        </nav>
        <p className="side-note">Read-only view of the PostgreSQL database</p>
      </aside>
      <main>
        <h1>{page}</h1>
        <Page />
      </main>
    </div>
  );
}
