import Link from "next/link";

export default function Home() {
  return (
    <main className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">PandaAlpha A 阶段</h1>
      <div className="space-x-4">
        <Link className="underline" href="/watchlist">Watchlist</Link>
        <Link className="underline" href="/stock/600519.SH">Stock Detail: 600519.SH</Link>
      </div>
    </main>
  );
}
