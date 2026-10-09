import { useEffect, useState } from "react";

export async function api(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null));
  const res = await fetch(`/api${path}${qs.size ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(res.status === 404 ? "Not found" : `Request failed (${res.status})`);
  return res.json();
}

// { data, error, loading } for one GET; refetches when path or params change
export function useApi(path, params) {
  const [state, set] = useState({ data: null, error: null, loading: true });
  const key = path + JSON.stringify(params ?? {});
  useEffect(() => {
    let stale = false;
    set((s) => ({ ...s, loading: true }));
    api(path, params)
      .then((data) => !stale && set({ data, error: null, loading: false }))
      .catch((error) => !stale && set({ data: null, error, loading: false }));
    return () => { stale = true; };
  }, [key]);
  return state;
}

const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const usd2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
export const usd = (n) => usd0.format(n ?? 0);
export const usdExact = (n) => (n == null ? "" : usd2.format(n));
export const num = (n) => (n == null ? "" : new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 }).format(n));
export const pct = (n) => (n == null ? "" : `${n > 0 ? "+" : ""}${Number(n).toFixed(2)}%`);
export const compact = (n) => new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
