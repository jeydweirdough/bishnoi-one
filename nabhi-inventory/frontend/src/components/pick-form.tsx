"use client";

import { Button } from "@/src/platform/ui/button";
import { FormError, Select, Textarea } from "@/src/platform/ui/field";
import { useState } from "react";
import { dispatchTransfer, issueOrder } from "../actions/inventory";
import type { ProductRef } from "../lib/types";
import { useSave } from "./lines";

export type PickLine = { id: string; product: ProductRef; quantity: number; batches: { id: string; label: string }[] };

/**
 * Taking stock out for an order or a transfer. Batches go first-expired-first-out
 * unless someone picks one; serial-numbered units need their numbers.
 */
export function PickForm({ kind, documentId, lines, label }: { kind: "order" | "transfer"; documentId: string; lines: PickLine[]; label: string }) {
  const { pending, error, fields, save } = useSave();
  const [chosen, setChosen] = useState<Record<string, { batchId: string; serials: string }>>({});
  const needsChoice = lines.some((l) => l.product.trackBatches || l.product.trackSerials);

  function submit() {
    const input = {
      lines: lines.map((l) => ({
        lineId: l.id,
        batchId: chosen[l.id]?.batchId || null,
        serials: (chosen[l.id]?.serials ?? "").split(/[\s,]+/).filter(Boolean),
      })),
    };
    save(() => (kind === "order" ? issueOrder(documentId, input) : dispatchTransfer(documentId, input)), () => ({ message: kind === "order" ? "Issued: stock is out" : "Dispatched: it's in transit" }));
  }

  return (
    <div className="space-y-3">
      {needsChoice && (
        <ul className="divide-y divide-rule">
          {lines.filter((l) => l.product.trackBatches || l.product.trackSerials).map((l) => {
            const c = chosen[l.id] ?? { batchId: "", serials: "" };
            const set = (change: Partial<typeof c>) => setChosen({ ...chosen, [l.id]: { ...c, ...change } });
            return (
              <li key={l.id} className="grid gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_14rem_minmax(0,1fr)] sm:items-start">
                <span className="text-sm font-semibold">{l.product.name}<span className="block text-meta font-normal text-ink-3">{l.quantity} {l.product.unit}</span></span>
                {l.product.trackBatches ? (
                  <Select aria-label={`${l.product.name} batch`} value={c.batchId} onChange={(e) => set({ batchId: e.target.value })}>
                    <option value="">First expired, first out</option>
                    {l.batches.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
                  </Select>
                ) : <span />}
                {l.product.trackSerials ? (
                  <Textarea aria-label={`${l.product.name} serial numbers`} rows={2} placeholder={`${l.quantity} serial number${l.quantity === 1 ? "" : "s"}`} value={c.serials} onChange={(e) => set({ serials: e.target.value })} className="font-mono text-meta" />
                ) : <span />}
              </li>
            );
          })}
        </ul>
      )}
      <FormError message={error ?? fields.lines} />
      <Button variant="primary" loading={pending} onClick={submit}>{label}</Button>
    </div>
  );
}
