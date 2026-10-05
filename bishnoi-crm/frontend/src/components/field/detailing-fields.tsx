"use client";

import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { Field, Input, Select } from "@/src/platform/ui/field";
import { visitBrief } from "../../actions/field";
import type { Reaction, VisitBrief } from "./types";
import { REACTIONS } from "./words";

export type DetailDraft = { key: number; productId: string; message: string; reaction: Reaction | "" };

let next = 0;
export const newDetail = (): DetailDraft => ({ key: next++, productId: "", message: "", reaction: "" });

/**
 * The structured part of a visit (P6): what the last visit set out to do,
 * the products discussed in the order they were, each with its key message
 * and how the doctor took it, and what the next visit is for.
 */
export function DetailingFields({
  companyId,
  rows,
  onRows,
  objective,
  onObjective,
  errors,
}: {
  companyId: string;
  rows: DetailDraft[];
  onRows: (rows: DetailDraft[]) => void;
  objective: string;
  onObjective: (text: string) => void;
  errors: Record<string, string>;
}) {
  const [brief, setBrief] = useState<VisitBrief | null>(null);

  useEffect(() => {
    let current = true;
    if (!companyId) return;
    visitBrief(companyId).then((r) => current && setBrief(r.ok ? r.data : null));
    return () => {
      current = false;
    };
  }, [companyId]);

  const set = (key: number, change: Partial<DetailDraft>) => onRows(rows.map((r) => (r.key === key ? { ...r, ...change } : r)));
  const move = (i: number, by: number) => {
    const out = [...rows];
    [out[i], out[i + by]] = [out[i + by], out[i]];
    onRows(out);
  };
  const taken = new Set(rows.map((r) => r.productId));
  const shownBrief = companyId ? brief : null;

  return (
    <div className="space-y-3">
      {shownBrief?.lastObjective && (
        <p className="rounded-[3px] border-l-4 border-hema bg-hema-tint px-3 py-2 text-sm">
          <span className="font-semibold">Last visit&apos;s objective:</span> {shownBrief.lastObjective.text}
        </p>
      )}
      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-medium text-ink">
          Products discussed <span className="font-normal text-ink-3">(optional, in the order you discussed them)</span>
        </legend>
        {rows.map((r, i) => (
          <div key={r.key} className="rounded-[3px] border border-rule p-2.5">
            <div className="flex items-start gap-2">
              <span className="pt-2 text-meta font-semibold text-ink-3 tabular-nums">{i + 1}.</span>
              <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-2">
                <Field label="Product" error={errors[`detailing.${i}.productId`]}>
                  {(p) => (
                    <Select {...p} value={r.productId} onChange={(e) => set(r.key, { productId: e.target.value })}>
                      <option value="">Pick a product</option>
                      {(shownBrief?.products ?? []).map((prod) => (
                        <option key={prod.id} value={prod.id} disabled={taken.has(prod.id) && prod.id !== r.productId}>
                          {prod.name}
                          {prod.strength ? ` ${prod.strength}` : ""}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label="How the doctor took it" error={errors[`detailing.${i}.reaction`]}>
                  {(p) => (
                    <Select {...p} value={r.reaction} onChange={(e) => set(r.key, { reaction: e.target.value as Reaction })}>
                      <option value="">Pick one</option>
                      {REACTIONS.map((x) => (
                        <option key={x.value} value={x.value}>
                          {x.label}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <div className="sm:col-span-2">
                  <Field label="Key message" optional error={errors[`detailing.${i}.message`]}>
                    {(p) => <Input {...p} value={r.message} onChange={(e) => set(r.key, { message: e.target.value })} maxLength={300} placeholder="What you told them about it" />}
                  </Field>
                </div>
              </div>
              <div className="flex flex-col gap-0.5">
                <button type="button" onClick={() => move(i, -1)} disabled={i === 0} className="rounded-[3px] p-1 text-ink-3 hover:bg-bench disabled:opacity-30" aria-label="Discussed earlier">
                  <ArrowUp className="size-3.5" aria-hidden />
                </button>
                <button type="button" onClick={() => move(i, 1)} disabled={i === rows.length - 1} className="rounded-[3px] p-1 text-ink-3 hover:bg-bench disabled:opacity-30" aria-label="Discussed later">
                  <ArrowDown className="size-3.5" aria-hidden />
                </button>
                <button type="button" onClick={() => onRows(rows.filter((x) => x.key !== r.key))} className="rounded-[3px] p-1 text-ink-3 hover:bg-bench hover:text-danger" aria-label="Take this product off">
                  <X className="size-3.5" aria-hidden />
                </button>
              </div>
            </div>
          </div>
        ))}
        {rows.length < 10 && (
          <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => onRows([...rows, newDetail()])} disabled={!companyId}>
            {rows.length ? "Another product" : "Add a product discussed"}
          </Button>
        )}
      </fieldset>
      <Field label="Next visit's objective" optional hint="Shown when the next visit to this doctor is logged." error={errors.nextObjective}>
        {(p) => <Input {...p} value={objective} onChange={(e) => onObjective(e.target.value)} maxLength={300} placeholder="e.g. Bring the dosing study" />}
      </Field>
    </div>
  );
}
