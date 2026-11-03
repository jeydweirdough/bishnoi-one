import { NextRequest } from "next/server";
import { accountToken, PLATFORM_API } from "@/src/platform/lib/account";
import { cookies } from "next/headers";
import { MODULES } from "@/src/platform/lib/modules";
import { viewAsCookie } from "@/src/platform/lib/session-cookie";
import { isSameOriginRequest } from "@/src/platform/lib/site";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: NextRequest) {
  if (!isSameOriginRequest(request)) return Response.json({ error: "Cross-site assistant requests are refused." }, { status: 403 });
  if (!request.headers.get("content-type")?.startsWith("application/json")) return Response.json({ error: "Send a JSON question." }, { status: 415 });
  const token = await accountToken();
  if (!token) return Response.json({ error: "Please sign in again." }, { status: 401 });
  const jar = await cookies();
  if (MODULES.some(m => jar.get(viewAsCookie(m.key))?.value)) return Response.json({ error: "Stop View as before using the assistant with your own account." }, { status: 409 });
  const reader = request.body?.getReader();
  if (!reader) return Response.json({ error: "Enter a question." }, { status: 400 });
  const decoder = new TextDecoder();
  let raw = "", bytes = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      bytes += chunk.value.byteLength;
      if (bytes > 20000) { await reader.cancel(); return Response.json({ error: "This conversation is too long. Start a new chat." }, { status: 413 }); }
      raw += decoder.decode(chunk.value, { stream: true });
    }
    raw += decoder.decode();
    JSON.parse(raw);
  } catch { return Response.json({ error: "Invalid question JSON." }, { status: 400 }); }
  try {
    const upstream = await fetch(`${PLATFORM_API}/identity/assistant/chat`, {
      method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: raw, cache: "no-store", redirect: "error",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(50000)]),
    });
    if (!upstream.ok) {
      const data = await upstream.json().catch(() => null);
      return Response.json({ error: typeof data?.detail === "string" ? data.detail : "The assistant could not accept this request." }, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
    }
    return new Response(upstream.body, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-store", "X-Accel-Buffering": "no" } });
  } catch {
    return Response.json({ error: "The assistant is unavailable or timed out. Try again later." }, { status: 503 });
  }
}
