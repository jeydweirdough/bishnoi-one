"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { Sheet } from "@/src/platform/ui/sheet";
import { Textarea } from "@/src/platform/ui/field";
import { readAssistantStream, type AssistantSource } from "./stream";

type Turn = { question: string; text: string; sources: AssistantSource[]; range?: { from: string; to: string } | null; definitions?: Record<string, string> | null; retrievedAt?: string; error?: string; done?: boolean };
const examples = ["Who is our CEO?", "Show our revenue, expenses and profit for last month."];

export function AssistantChat({ companyId, companyName }: { companyId: string; companyName: string }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "nearest" }); }, [turns, status]);

  async function send() {
    const message = question.trim();
    if (!message || busy || abort.current) return;
    const controller = new AbortController();
    abort.current = controller;
    setQuestion(""); setBusy(true); setStatus("Connecting...");
    const index = turns.length;
    setTurns(previous => [...previous, { question: message, text: "", sources: [] }]);
    const edit = (change: Partial<Turn>) => setTurns(previous => previous.map((turn, i) => i === index ? { ...turn, ...change } : turn));
    let answer = "";
    try {
      const response = await fetch("/api/assistant/chat", { method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ companyId, message, history: turns.filter(t => t.done).slice(-3).map(t => t.question) }) });
      if (!response.ok || !response.headers.get("content-type")?.includes("text/event-stream") || !response.body) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.error ?? "The assistant could not connect. Check your sign-in and try again.");
      }
      await readAssistantStream(response.body, event => {
        if (event.type === "status") setStatus(event.message ?? "Reading...");
        if (event.type === "text") { answer += event.text ?? ""; edit({ text: answer }); }
        if (event.type === "sources") edit({ sources: event.items ?? [], range: event.dateRange, definitions: event.definitions, retrievedAt: event.retrievedAt });
        if (event.type === "done") edit({ done: true });
        if (event.type === "error") edit({ error: event.message ?? "No verified answer is available." });
      });
    } catch (error) {
      edit({ error: controller.signal.aborted ? "Stopped. This response may be incomplete." : error instanceof Error ? error.message : "The assistant could not complete this response." });
    } finally { abort.current = null; setBusy(false); setStatus(""); }
  }

  return <div className="mx-auto max-w-4xl space-y-4">
    <Sheet className="space-y-2 px-5 py-4">
      <h2 className="text-heading">Ask about {companyName}</h2>
      <p className="text-sm text-ink-3">Read-only company directory and monthly financial lookups. Your permissions apply. Figures and employee details come from recorded sources; the AI cannot change business records. Chats stay in this tab and clear when you leave or switch company.</p>
      <div className="flex flex-wrap gap-2">{examples.map(example => <Button key={example} size="sm" disabled={busy} onClick={() => setQuestion(example)}>{example}</Button>)}</div>
    </Sheet>
    <div aria-label="Assistant conversation" className="space-y-4">
      {turns.map((turn, i) => <Sheet key={i} className="space-y-3 px-5 py-4">
        <h3 className="font-semibold text-ink">{turn.question}</h3>
        {turn.text && <div className="whitespace-pre-wrap text-sm leading-6">{turn.text}</div>}
        {turn.error && <p role="alert" className="text-sm text-danger">{turn.error}</p>}
        {turn.range && <p className="text-xs text-ink-3">Date range: {turn.range.from} to {turn.range.to}, inclusive.</p>}
        {turn.sources.length > 0 && <div className="border-t border-rule pt-3 text-xs text-ink-3"><p className="font-medium">Sources</p><ul className="mt-1 space-y-1">{turn.sources.map((source, n) => <li key={n}>{source.href?.startsWith("/") && !source.href.startsWith("//") ? <Link className="underline" href={source.href}>{source.label}</Link> : <span>{source.label}{source.reference ? ` (${source.reference})` : ""}</span>}</li>)}</ul></div>}
        {turn.retrievedAt && <p className="text-xs text-ink-3">Read at {new Date(turn.retrievedAt).toLocaleString()}.</p>}
        {turn.definitions && <details className="text-xs text-ink-3"><summary className="cursor-pointer">Accounting definitions</summary><ul className="mt-2 space-y-1">{Object.entries(turn.definitions).map(([key, value]) => <li key={key}><strong>{key}: </strong>{value}</li>)}</ul></details>}
      </Sheet>)}
      <div ref={bottom} />
    </div>
    {status && <p role="status" aria-live="polite" className="text-sm text-ink-3">{status}</p>}
    <Sheet className="space-y-3 px-5 py-4"><form onSubmit={event => { event.preventDefault(); void send(); }} className="space-y-3">
      <label htmlFor="assistant-question" className="block text-sm font-medium">Your question</label>
      <Textarea id="assistant-question" rows={3} maxLength={2000} value={question} disabled={busy} onChange={event => setQuestion(event.target.value)} placeholder="Ask for a recorded employee or job title, or monthly financials..." />
      <div className="flex flex-wrap gap-2"><Button variant="primary" type="submit" disabled={busy || !question.trim()}>Send question</Button>{busy && <Button onClick={() => abort.current?.abort()}>Stop</Button>}<Button disabled={busy || turns.length === 0} onClick={() => setTurns([])}>New chat</Button></div>
    </form></Sheet>
  </div>;
}
