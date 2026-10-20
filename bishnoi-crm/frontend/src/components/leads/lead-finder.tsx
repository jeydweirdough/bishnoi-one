"use client";

import { ClipboardPaste, Copy, ExternalLink, Search, Sparkles, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { checkLeads, saveLeads, type Lead, type LeadCheck } from "@/src/actions/leads";
import { Button } from "@/src/platform/ui/button";
import { Field, Input, Select, Textarea } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { CHATBOTS, leadPrompt, readPasted } from "./prompt";

// Find leads with AI (decided 2026-10-19): 1. say what to look for; 2. open
// the prompt in ChatGPT, Claude or DeepSeek (the prompt is copied too); 3.
// paste the chatbot's answer; 4. tick the ones to keep. Nothing is saved
// until step 4, and each lead keeps the page it was found on.

type Row = { lead: Lead; check: LeadCheck | null; keep: boolean };
const COUNTS = [10, 20, 50];

export function LeadFinder({ company, team, types, defaultWhere }: { company: string; team: string | null; types: { code: string; name: string }[]; defaultWhere: string }) {
  const [where, setWhere] = useState(defaultWhere);
  const [kinds, setKinds] = useState<string[]>(types.slice(0, 3).map((t) => t.code));
  const [focus, setFocus] = useState("");
  const [count, setCount] = useState(20);
  const [pasted, setPasted] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [saved, setSaved] = useState<{ id: string; name: string }[]>([]);
  const [checking, startCheck] = useTransition();
  const [saving, startSave] = useTransition();

  const chosen = types.filter((t) => kinds.includes(t.code));
  const prompt = useMemo(() => leadPrompt({ where, types: chosen.length ? chosen : types, focus, count, company, team }), [where, chosen, types, focus, count, company, team]);
  const typeName = (code: string | null | undefined) => types.find((t) => t.code === code)?.name;

  async function copy(): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(prompt);
      return true;
    } catch {
      return false;
    }
  }
  async function open(bot: (typeof CHATBOTS)[number]) {
    const copied = await copy();
    window.open(bot.url(prompt), "_blank", "noopener");
    toast.success(bot.prefills ? `Opened ${bot.label}: press Enter to run it` : `Prompt copied: paste it in ${bot.label} (Ctrl+V), then Enter`, {
      description: copied ? "The prompt is also on your clipboard if the box comes up empty." : undefined,
    });
  }

  function read() {
    const leads = readPasted(pasted);
    if (leads.length === 0) {
      toast.error("No leads found in what you pasted.", { description: "Copy the chatbot's whole answer (its code block) and paste it here." });
      return;
    }
    startCheck(async () => {
      const r = await checkLeads(leads.slice(0, 100));
      if (!r.ok) {
        toast.error(r.error);
        return;
      }
      setSaved([]);
      setRows(
        leads.slice(0, 100).map((lead, i) => {
          const check = r.data[i] ?? null;
          return { lead: { ...lead, type: check?.type ?? null }, check, keep: !!check && check.matches.length === 0 && !check.problems.some((p) => p.startsWith("No source")) };
        }),
      );
    });
  }

  function save() {
    const picked = rows.filter((r) => r.keep);
    if (picked.length === 0) {
      toast.error("Tick the leads to add.");
      return;
    }
    startSave(async () => {
      const r = await saveLeads(picked.map((x) => x.lead));
      if (!r.ok) {
        toast.error(r.error);
        return;
      }
      setSaved(r.data.saved);
      const savedNames = new Set(r.data.saved.map((s) => s.name));
      setRows((rs) => rs.filter((x) => !(x.keep && savedNames.has(x.lead.name.trim()))));
      toast.success(`${r.data.saved.length} added to your customers`, {
        description: r.data.skipped.length ? `${r.data.skipped.length} skipped: ${r.data.skipped.map((s) => `${s.name} (${s.why})`).join("; ")}` : "Each has a call to make in two days.",
      });
    });
  }

  const set = (i: number, change: Partial<Lead>) => setRows((rs) => rs.map((r, n) => (n === i ? { ...r, lead: { ...r.lead, ...change } } : r)));
  const tick = (i: number, keep: boolean) => setRows((rs) => rs.map((r, n) => (n === i ? { ...r, keep } : r)));

  return (
    <div className="space-y-5">
      {/* 1. What to look for */}
      <Sheet className="px-5 py-4">
        <SectionTitle icon="trend">1. What to look for</SectionTitle>
        <div className="mt-3 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_10rem]">
          <Field label="Where">{(p) => <Input {...p} value={where} onChange={(e) => setWhere(e.target.value)} placeholder="e.g. Davao City, or Region IV-A" />}</Field>
          <Field label="Product focus" optional>{(p) => <Input {...p} value={focus} onChange={(e) => setFocus(e.target.value)} placeholder="e.g. oncology, anesthesia" />}</Field>
          <Field label="How many">
            {(p) => (
              <Select {...p} value={String(count)} onChange={(e) => setCount(Number(e.target.value))}>
                {COUNTS.map((c) => (
                  <option key={c} value={c}>
                    Up to {c}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <fieldset className="mt-4">
          <legend className="mb-1.5 text-sm font-medium text-ink">Kinds of business</legend>
          <div className="flex flex-wrap gap-1.5">
            {types.map((t) => {
              const on = kinds.includes(t.code);
              return (
                <button
                  key={t.code}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setKinds((k) => (on ? k.filter((x) => x !== t.code) : [...k, t.code]))}
                  className={`h-8 rounded-full border px-3 text-meta transition-colors ${on ? "border-ink bg-ink font-semibold text-white" : "border-rule-strong bg-sheet text-ink-2 hover:border-ink"}`}
                >
                  {t.name}
                </button>
              );
            })}
          </div>
        </fieldset>
      </Sheet>

      {/* 2. Ask your chatbot */}
      <Sheet className="px-5 py-4">
        <SectionTitle icon="message">2. Ask your AI</SectionTitle>
        <p className="mt-1 text-meta text-ink-3">Opens your chatbot with this prompt ready. Press Enter there. Turn on web search if it asks.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {CHATBOTS.map((bot) => (
            <Button key={bot.key} variant={bot.key === "chatgpt" ? "primary" : "default"} icon={<ExternalLink className="size-4" aria-hidden />} onClick={() => open(bot)}>
              Open in {bot.label}
            </Button>
          ))}
          <Button
            variant="quiet"
            icon={<Copy className="size-4" aria-hidden />}
            onClick={async () => ((await copy()) ? toast.success("Prompt copied") : toast.error("Couldn't copy: select the prompt below and copy it."))}
          >
            Copy prompt
          </Button>
        </div>
        <details className="mt-3">
          <summary className="cursor-pointer text-meta text-ink-2 hover:text-ink">See the prompt</summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-bench p-3 text-[0.75rem] whitespace-pre-wrap text-ink-2">{prompt}</pre>
        </details>
      </Sheet>

      {/* 3. Paste what it found */}
      <Sheet className="px-5 py-4">
        <SectionTitle icon="logActivity">3. Paste what it found</SectionTitle>
        <p className="mt-1 text-meta text-ink-3">Click Copy on the chatbot&apos;s code block, then paste here. A table or CSV works too.</p>
        <Textarea className="mt-3 font-mono text-[0.8125rem]" rows={7} value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="Paste the AI's answer here" />
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="primary" icon={<Search className="size-4" aria-hidden />} loading={checking} disabled={!pasted.trim()} onClick={read}>
            Check leads
          </Button>
          <Button
            variant="quiet"
            icon={<ClipboardPaste className="size-4" aria-hidden />}
            onClick={async () => {
              try {
                setPasted(await navigator.clipboard.readText());
              } catch {
                toast.error("Your browser didn't allow it: paste with Ctrl+V.");
              }
            }}
          >
            Paste from clipboard
          </Button>
        </div>
      </Sheet>

      {/* 4. Choose which to add */}
      {(rows.length > 0 || saved.length > 0) && (
        <Sheet className="px-5 py-4">
          <SectionTitle
            icon="customers"
            action={
              rows.length > 0 && (
                <Button variant="primary" icon={<Sparkles className="size-4" aria-hidden />} loading={saving} onClick={save}>
                  Add {rows.filter((r) => r.keep).length} to my customers
                </Button>
              )
            }
          >
            4. Choose which to add
          </SectionTitle>
          {saved.length > 0 && (
            <p className="mt-2 rounded-lg bg-mint px-3 py-2 text-meta text-ink">
              Added: {saved.map((s, i) => (
                <span key={s.id}>
                  {i > 0 && ", "}
                  <Link href={`/companies/${s.id}`} className="font-medium underline-offset-4 hover:underline">
                    {s.name}
                  </Link>
                </span>
              ))}
              .
            </p>
          )}
          {rows.length > 0 && (
            <>
              <p className="mt-1 text-meta text-ink-3">Leads that look like a customer already in the CRM, or have no source, start unticked. Check each source before adding.</p>
              <ul className="mt-3 divide-y divide-rule">
                {rows.map((r, i) => (
                  <li key={i} className="grid gap-3 py-3 lg:grid-cols-[auto_minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1.2fr)]">
                    <input type="checkbox" checked={r.keep} onChange={(e) => tick(i, e.target.checked)} aria-label={`Add ${r.lead.name}`} className="mt-2 size-4 accent-[var(--color-ink)]" />
                    <div className="min-w-0 space-y-1.5">
                      <Input value={r.lead.name} onChange={(e) => set(i, { name: e.target.value })} aria-label="Name" />
                      <div className="grid grid-cols-2 gap-1.5">
                        <Input value={r.lead.city ?? ""} onChange={(e) => set(i, { city: e.target.value })} placeholder="City" aria-label="City" />
                        <Input value={r.lead.phone ?? ""} onChange={(e) => set(i, { phone: e.target.value })} placeholder="Phone" aria-label="Phone" />
                      </div>
                      {r.lead.address && <p className="truncate text-meta text-ink-3">{r.lead.address}</p>}
                    </div>
                    <div className="min-w-0 space-y-1.5">
                      <Select value={r.lead.type ?? ""} onChange={(e) => set(i, { type: e.target.value || null })} aria-label="Type">
                        <option value="">Type: your team&apos;s first</option>
                        {types.map((t) => (
                          <option key={t.code} value={t.code}>
                            {t.name}
                          </option>
                        ))}
                      </Select>
                      {r.lead.why && <p className="text-meta text-ink-2">{r.lead.why}</p>}
                    </div>
                    <div className="min-w-0 space-y-1 text-meta">
                      {r.lead.source ? (
                        <a href={r.lead.source} target="_blank" rel="noopener noreferrer" className="inline-flex max-w-full items-center gap-1 text-ink underline-offset-4 hover:underline">
                          <ExternalLink className="size-3.5 shrink-0" aria-hidden />
                          <span className="truncate">{r.lead.source.replace(/^https?:\/\//, "")}</span>
                        </a>
                      ) : null}
                      {r.check?.matches.map((m, n) => (
                        <p key={n} className="flex items-start gap-1.5 text-[#8a5a00]">
                          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                          <span>
                            Already in the CRM:{" "}
                            {m.id ? (
                              <Link href={`/companies/${m.id}`} className="font-medium underline-offset-4 hover:underline">
                                {m.name}
                              </Link>
                            ) : (
                              m.name
                            )}
                            {m.teamName ? ` · ${m.teamName}` : ""} ({m.why.join(", ").toLowerCase()})
                          </span>
                        </p>
                      ))}
                      {r.check?.problems.map((p) => (
                        <p key={p} className="text-ink-3">
                          {p}
                        </p>
                      ))}
                      {r.lead.type && <p className="text-ink-3">As: {typeName(r.lead.type)}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Sheet>
      )}
    </div>
  );
}
