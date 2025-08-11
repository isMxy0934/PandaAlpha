"use client";
import React, { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

type PricesResp = { adj: string; rows: { ts_code: string; trade_date: string; open: number; high: number; low: number; close: number; volume?: number; amount?: number; turnover_rate?: number | null }[] };
type MetricsResp = { ts_code: string; rows: { trade_date: string; ma20?: number | null; vol_ann?: number | null; turnover?: number | null }[] };

async function fetchPrices(ts: string): Promise<PricesResp> {
  const url = `/api/panda/api/prices?ts_code=${ts}&start=2025-06-01&end=2025-08-08&include_basic=true`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("failed");
  return res.json();
}

async function fetchMetrics(ts: string): Promise<MetricsResp> {
  const url = `/api/panda/api/metrics?ts_code=${ts}&window=20&metrics=ma,vol_ann,turnover&start=2025-06-01&end=2025-08-08`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("failed");
  return res.json();
}

export default function StockDetailPage() {
  const params = useParams<{ ts_code: string }>();
  const ts = params.ts_code;
  const { data: prices, isLoading: loadingP } = useQuery({ queryKey: ["prices", ts], queryFn: () => fetchPrices(ts) });
  const { data: metrics, isLoading: loadingM } = useQuery({ queryKey: ["metrics", ts], queryFn: () => fetchMetrics(ts) });

  const chartData = useMemo(() => {
    const pmap = new Map<string, number>();
    prices?.rows?.forEach(r => {
      if (r.close != null) pmap.set(r.trade_date, r.close);
    });
    const out: { trade_date: string; close?: number; ma20?: number | null }[] = [];
    metrics?.rows?.forEach(m => {
      out.push({ trade_date: m.trade_date, close: pmap.get(m.trade_date), ma20: (m as any).ma20 ?? null });
    });
    return out;
  }, [prices, metrics]);

  return (
    <main className="p-6 space-y-4">
      <h1 className="text-xl font-bold">{ts}</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="md:col-span-2">
          <h2 className="font-semibold mb-2">Close vs MA20</h2>
          {(loadingP || loadingM) ? (
            <p>加载中...</p>
          ) : (
            <div className="h-72 bg-white p-2 rounded">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
                  <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} hide={false} interval={chartData.length > 30 ? 4 : 0} />
                  <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="close" stroke="#2563eb" dot={false} strokeWidth={1.5} />
                  <Line type="monotone" dataKey="ma20" stroke="#16a34a" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
        <section>
          <h2 className="font-semibold mb-2">Prices (head)</h2>
          {loadingP ? <p>加载中...</p> : <pre className="text-xs bg-gray-100 text-black p-3 rounded overflow-auto">{JSON.stringify(prices?.rows?.slice(0, 5) || [], null, 2)}</pre>}
        </section>
        <section>
          <h2 className="font-semibold mb-2">Metrics (tail)</h2>
          {loadingM ? <p>加载中...</p> : <pre className="text-xs bg-gray-100 text-black p-3 rounded overflow-auto">{JSON.stringify(metrics?.rows?.slice(-5) || [], null, 2)}</pre>}
        </section>
      </div>
    </main>
  );
}


