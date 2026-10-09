import { ResponsiveContainer } from "recharts";

export function Panel({ title, children, aside }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{title}</h2>
        {aside}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

// Renders loading / error, or calls children(data) once data is there
export function Async({ state, children }) {
  if (state.error) return <p className="msg bad">{state.error.message}</p>;
  if (!state.data) return <p className="msg blink">Loading</p>;
  return children(state.data);
}

export function Stat({ label, value, tone }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}

// columns: [{ key, label, right?, render?(row) }]
export function DataTable({ columns, rows, empty = "No rows match." }) {
  if (!rows.length) return <p className="msg">{empty}</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((c) => <th key={c.key} className={c.right ? "r" : ""}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={c.right ? "r" : ""}>{c.render ? c.render(row) : row[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const tone = (n) => (n > 0 ? "gain" : n < 0 ? "loss" : "");

export const Chart = ({ children, height = 240 }) => (
  <ResponsiveContainer width="100%" height={height}>{children}</ResponsiveContainer>
);

export const axis = { tick: { fontFamily: "VT323", fontSize: 16, fill: "#6b6b6b" }, stroke: "#242424", tickLine: false };
export const tooltip = {
  contentStyle: { background: "#ffffff", border: "2px solid #6d28d9", borderRadius: 0, fontFamily: "VT323", fontSize: 18, color: "#171717" },
  labelStyle: { color: "#171717" },
  cursor: { fill: "rgba(109,40,217,.12)" },
};
