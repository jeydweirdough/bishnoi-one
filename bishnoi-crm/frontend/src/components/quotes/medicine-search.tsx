"use client";

import { Minus, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState, useTransition, type ReactNode } from "react";
import { Button, IconButton, TextButton } from "@/src/platform/ui/button";
import { Empty } from "@/src/platform/ui/sheet";
import { FormError, Textarea } from "@/src/platform/ui/field";
import type { OrderLine } from "../../actions/quote-links";

export type Medicine = { id: string; code: string; name: string; genericName: string | null; strength: string | null; form: string | null; unit: string | null; priceCentavos: number };

const peso = new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" });
const money = (centavos: number) => peso.format(centavos / 100);
const words = (m: Medicine) => [m.genericName && m.genericName !== m.name ? m.genericName : null, m.strength, m.form].filter(Boolean).join(" · ");

/**
 * Find a medicine by its name (brand or generic) or code, see its details and
 * price, pick how many; the picks add up on the right; then send. The same on
 * a customer's order link and a rep's quick quote: only what's sent differs.
 */
export function MedicineSearch({
  medicines,
  submitLabel,
  withNote = false,
  before,
  missing = null,
  withAsk = false,
  onSubmit,
}: {
  medicines: Medicine[];
  submitLabel: string;
  /** A note to send with it (the customer's order). */
  withNote?: boolean;
  /** More the order needs, above the picks (who's ordering, on a link for someone not a customer yet). */
  before?: ReactNode;
  /** Why it can't be sent yet, said under the button. */
  missing?: string | null;
  /** Each pick can ask for another price (a customer's order link): the rep decides. */
  withAsk?: boolean;
  onSubmit: (lines: OrderLine[], note: string | null) => Promise<string | null>;
}) {
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<Record<string, number>>({});
  // Asked prices, per medicine, as typed (pesos): only those under the shown price count.
  const [asking, setAsking] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const byId = useMemo(() => new Map(medicines.map((m) => [m.id, m])), [medicines]);
  const found = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return [];
    return medicines.filter((m) => [m.name, m.genericName, m.code].some((x) => x?.toLowerCase().includes(t))).slice(0, 30);
  }, [q, medicines]);
  const chosen = Object.entries(picked).filter(([, n]) => n > 0);
  const askedOf = (id: string): number | null => {
    const typed = asking[id];
    if (typed === undefined || !typed.trim()) return null;
    const centavos = Math.round(Number(typed.replace(/[^0-9.]/g, "")) * 100);
    const shown = byId.get(id)?.priceCentavos ?? 0;
    return centavos > 0 && centavos < shown ? centavos : null;
  };
  const unitOf = (id: string) => askedOf(id) ?? byId.get(id)?.priceCentavos ?? 0;
  const total = chosen.reduce((sum, [id, n]) => sum + unitOf(id) * n, 0);
  const anyAsked = chosen.some(([id]) => askedOf(id) !== null);
  const set = (id: string, n: number) => setPicked((p) => ({ ...p, [id]: Math.max(0, Math.min(100_000, n)) }));

  function send() {
    setError(null);
    start(async () => {
      const problem = await onSubmit(
        chosen.map(([productId, quantity]) => ({ productId, quantity, ...(askedOf(productId) ? { askedPriceCentavos: askedOf(productId)! } : {}) })),
        note.trim() || null,
      );
      if (problem) setError(problem);
    });
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
      {/* 1. Find it. */}
      <section aria-labelledby="find" className="rounded-sheet border border-rule bg-sheet p-5">
        <h2 id="find" className="text-heading text-ink">
          Find a medicine
        </h2>
        <label className="mt-3 flex h-12 items-center gap-3 rounded-full border border-control bg-sheet px-5 focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgb(168_214_155_/_0.45)]">
          <Search className="size-4 text-ink-3" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type its name, generic name or code" aria-label="Find a medicine" autoFocus className="w-full bg-transparent text-sm outline-none" />
        </label>
        {!q.trim() ? (
          <Empty compact icon="products" title="Search the medicines">
            {medicines.length} medicines, with their prices. Type a few letters of the one you need.
          </Empty>
        ) : found.length === 0 ? (
          <Empty compact icon="products" title={`Nothing called "${q.trim()}"`}>
            Try the generic name, or fewer letters.
          </Empty>
        ) : (
          <ul className="mt-3 divide-y divide-rule">
            {found.map((m) => (
              <li key={m.id} className="flex items-center gap-3 py-3">
                <span className="min-w-0 flex-1">
                  <span className="block font-medium text-ink">{m.name}</span>
                  <span className="block truncate text-meta text-ink-3">{[words(m), m.code].filter(Boolean).join(" · ")}</span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block text-sm font-semibold text-ink tabular-nums">{money(m.priceCentavos)}</span>
                  <span className="block text-meta text-ink-3">per {m.unit ?? "unit"}</span>
                </span>
                {picked[m.id] ? (
                  <Quantity value={picked[m.id]} onChange={(n) => set(m.id, n)} name={m.name} />
                ) : (
                  <Button size="sm" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => set(m.id, 1)}>
                    Add
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 2. What's picked, and what it comes to. */}
      <section aria-labelledby="picked" className="rounded-sheet border border-rule bg-sheet p-5 lg:sticky lg:top-6">
        {before}
        <h2 id="picked" className={`text-heading text-ink ${before ? "mt-6" : ""}`}>
          Your order
        </h2>
        {chosen.length === 0 ? (
          <p className="py-4 text-meta text-ink-3">Nothing yet. Add the medicines you need from the search.</p>
        ) : (
          <ul className="mt-2 divide-y divide-rule">
            {chosen.map(([id, n]) => {
              const m = byId.get(id)!;
              return (
                <li key={id} className="flex items-center gap-3 py-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-ink">{m.name}</span>
                    <span className="block text-meta text-ink-3 tabular-nums">
                      {askedOf(id) !== null ? (
                        <>
                          <s>{money(m.priceCentavos)}</s> {money(askedOf(id)!)} asked × {n} = {money(askedOf(id)! * n)}
                        </>
                      ) : (
                        <>
                          {money(m.priceCentavos)} × {n} = {money(m.priceCentavos * n)}
                        </>
                      )}
                    </span>
                    {withAsk &&
                      (asking[id] === undefined ? (
                        <TextButton onClick={() => setAsking((a) => ({ ...a, [id]: "" }))}>Ask for another price</TextButton>
                      ) : (
                        <span className="mt-1.5 flex items-center gap-2">
                          <span className="inline-flex h-8 items-center gap-1 rounded-full border border-control px-3 focus-within:border-ink">
                            <span className="text-meta text-ink-3">₱</span>
                            <input
                              value={asking[id]}
                              onChange={(e) => setAsking((a) => ({ ...a, [id]: e.target.value }))}
                              inputMode="decimal"
                              placeholder="0.00"
                              aria-label={`The price you ask for ${m.name}, per ${m.unit ?? "unit"}`}
                              autoFocus
                              className="w-20 bg-transparent text-sm tabular-nums outline-none"
                            />
                            <span className="text-meta text-ink-3">per {m.unit ?? "unit"}</span>
                          </span>
                          <TextButton tone="muted" onClick={() => setAsking((a) => { const next = { ...a }; delete next[id]; return next; })}>
                            Keep the price
                          </TextButton>
                        </span>
                      ))}
                  </span>
                  <Quantity value={n} onChange={(x) => set(id, x)} name={m.name} />
                  <IconButton label={`Remove ${m.name}`} tone="danger" size="sm" onClick={() => set(id, 0)}>
                    <Trash2 className="size-3.5" aria-hidden />
                  </IconButton>
                </li>
              );
            })}
          </ul>
        )}
        {anyAsked && <p className="mt-3 rounded-[14px] bg-mint px-3 py-2 text-meta text-ink-2">You asked for another price: your representative reviews it before the quotation is final. The total shows what you asked for.</p>}
        <div className="mt-3 flex items-baseline justify-between border-t border-rule-strong pt-3">
          <span className="text-sm font-medium text-ink">{anyAsked ? "Total, as asked" : "Total"}</span>
          <span className="text-[1.5rem] font-semibold text-ink tabular-nums">{money(total)}</span>
        </div>
        {withNote && (
          <label className="mt-4 block">
            <span className="mb-1.5 block text-sm font-medium text-ink">
              A note <span className="font-normal text-ink-3">(optional)</span>
            </span>
            <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder="e.g. Please deliver before Friday" />
          </label>
        )}
        <div className="mt-4 space-y-3">
          <FormError message={error} />
          <Button variant="primary" className="w-full" disabled={!chosen.length || Boolean(missing)} loading={pending} onClick={send}>
            {submitLabel}
          </Button>
          {chosen.length > 0 && missing && <p className="text-center text-meta text-ink-3">{missing}</p>}
        </div>
      </section>
    </div>
  );
}

/** How many: − the number +, the number typed in too. */
function Quantity({ value, onChange, name }: { value: number; onChange: (n: number) => void; name: string }) {
  return (
    <span className="inline-flex shrink-0 items-center rounded-full border border-rule-strong">
      <IconButton label={`One less ${name}`} size="sm" onClick={() => onChange(value - 1)}>
        <Minus className="size-3.5" aria-hidden />
      </IconButton>
      <input
        value={value}
        onChange={(e) => onChange(Number(e.target.value.replace(/\D/g, "")) || 0)}
        inputMode="numeric"
        aria-label={`How many ${name}`}
        className="w-10 bg-transparent text-center text-sm tabular-nums outline-none"
      />
      <IconButton label={`One more ${name}`} size="sm" onClick={() => onChange(value + 1)}>
        <Plus className="size-3.5" aria-hidden />
      </IconButton>
    </span>
  );
}
