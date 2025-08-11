"use client";
import React, { useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

type WatchlistResp = { page: number; limit: number; total: number; items: string[] };
type PriceRow = { ts_code: string; trade_date: string; close: number; volume?: number; amount?: number; turnover_rate?: number | null };
type PricesResp = { adj: string; rows: PriceRow[] };

async function fetchWatchlist(page = 1, limit = 100): Promise<WatchlistResp> {
  const res = await fetch(`/api/panda/api/watchlist?page=${page}&limit=${limit}`);
  if (!res.ok) throw new Error("failed");
  return res.json();
}

async function fetchLatestPrices(tsCodes: string[]): Promise<PricesResp> {
  if (tsCodes.length === 0) return { adj: "backward", rows: [] } as PricesResp;
  const ts = encodeURIComponent(tsCodes.join(","));
  // 近两个月区间
  const url = `/api/panda/api/prices?ts_code=${ts}&start=2025-06-01&end=2025-08-08&include_basic=true`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("failed");
  return res.json();
}

export default function WatchlistPage() {
  const wl = useQuery({ queryKey: ["watchlist"], queryFn: () => fetchWatchlist(1, 100) });
  const codes = wl.data?.items ?? [];
  const prices = useQuery({
    queryKey: ["prices", codes.join(",")],
    queryFn: () => fetchLatestPrices(codes),
    enabled: codes.length > 0,
  });

  const { latestMap, prevMap } = useMemo(() => {
    const lm = new Map<string, PriceRow>();
    const pm = new Map<string, PriceRow>();
    const rows = prices.data?.rows ?? [];
    for (const r of rows) {
      const cur = lm.get(r.ts_code);
      if (!cur || r.trade_date > cur.trade_date) {
        if (cur) pm.set(r.ts_code, cur);
        lm.set(r.ts_code, r);
      } else if (!pm.get(r.ts_code) || r.trade_date > (pm.get(r.ts_code)!.trade_date)) {
        pm.set(r.ts_code, r);
      }
    }
    return { latestMap: lm, prevMap: pm };
  }, [prices.data]);

  const fmt = (v: number | null | undefined, digits = 2) => (v ?? v === 0 ? Number(v).toFixed(digits) : "-");
  const fmtPct = (v: number | null | undefined) => (v ?? v === 0 ? (v as number).toFixed(2) + "%" : "-");

  return (
    <main className="p-6">
      <h1 className="text-xl font-bold mb-4">Watchlist</h1>
      {(wl.isLoading || prices.isLoading) && <p>加载中...</p>}
      {wl.error && <p className="text-red-600">自选加载失败</p>}
      {prices.error && <p className="text-red-600">行情加载失败</p>}
      <div className="overflow-auto rounded border">
        <table className="min-w-[860px] w-full text-sm">
          <thead className="sticky top-0 bg-white">
            <tr className="text-left border-b">
              <th className="py-2 px-3">代码</th>
              <th className="py-2 px-3">日期</th>
              <th className="py-2 px-3">收盘</th>
              <th className="py-2 px-3">涨跌幅</th>
              <th className="py-2 px-3">成交量</th>
              <th className="py-2 px-3">成交额</th>
              <th className="py-2 px-3">换手率(%)</th>
            </tr>
          </thead>
          <tbody>
            {codes.map((c) => {
              const r = latestMap.get(c);
              const p = prevMap.get(c);
              const pct = r?.close != null && p?.close != null ? ((r.close / p.close - 1) * 100) : null;
              const pctClass = pct == null ? "" : pct >= 0 ? "text-green-600" : "text-red-600";
              return (
                <tr key={c} className="border-b hover:bg-gray-50">
                  <td className="py-2 px-3"><Link className="underline" href={`/stock/${c}`}>{c}</Link></td>
                  <td className="py-2 px-3">{r?.trade_date ?? "-"}</td>
                  <td className="py-2 px-3">{fmt(r?.close)}</td>
                  <td className={`py-2 px-3 ${pctClass}`}>{pct == null ? "-" : fmtPct(pct)}</td>
                  <td className="py-2 px-3">{r?.volume ?? "-"}</td>
                  <td className="py-2 px-3">{r?.amount ?? "-"}</td>
                  <td className="py-2 px-3">{fmt(r?.turnover_rate)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </main>
  );
}


