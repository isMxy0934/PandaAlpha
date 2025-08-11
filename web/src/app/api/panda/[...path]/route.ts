import { NextRequest } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const targetPath = path.join("/");
  const url = new URL(req.url);
  const query = url.search;
  const target = `${API_BASE}/${targetPath}${query}`;
  const resp = await fetch(target, { headers: { Accept: "application/json" } });
  const body = await resp.text();
  return new Response(body, { status: resp.status, headers: { "content-type": resp.headers.get("content-type") || "application/json" } });
}


