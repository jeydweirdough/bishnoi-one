"use client";

import { CalendarClock, Play, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { deleteCountSchedule, saveCountSchedule, startScheduledCount } from "@/src/modules/inventory/actions/inventory";
import type { CountSchedule, Reference } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";

// Scheduled cycle counts (feature plan step 14b): counts that come round every so many days, so stock is
// counted a little at a time. Due ones start in one click; approving the count sets the next day.

const EVERY = [
  { days: 7, label: "Every week" },
  { days: 14, label: "Every 2 weeks" },
  { days: 30, label: "Every month" },
  { days: 90, label: "Every quarter" },
  { days: 180, label: "Every 6 months" },
  { days: 365, label: "Every year" },
];

const every = (days: number) => EVERY.find((e) => e.days === days)?.label ?? `Every ${days} days`;

export function CountSchedules({ schedules, reference, may }: {
  /** With their days written the company's way, by the page. */
  schedules: (CountSchedule & { nextLabel: string; lastLabel: string | null })[];
  reference: Pick<Reference, "categories" | "warehouses">;
  may: { create: boolean; manage: boolean };
}) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [adding, setAdding] = useState(false);
  const warehouses = reference.warehouses.filter((w) => w.isActive);
  const [form, setForm] = useState({ name: "", warehouseId: warehouses[0]?.id ?? "", categoryId: "", everyDays: "30", nextOn: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function add() {
    start(async () => {
      const r = await saveCountSchedule(null, {
        name: form.name.trim(), warehouseId: form.warehouseId, categoryId: form.categoryId || null, everyDays: Number(form.everyDays), nextOn: form.nextOn || null,
      });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success(`${form.name.trim()} scheduled`);
      setAdding(false);
      setForm({ ...form, name: "", categoryId: "", nextOn: "" });
      setFields({});
      setError(null);
      router.refresh();
    });
  }

  function begin(s: CountSchedule) {
    start(async () => {
      const r = await startScheduledCount(s.id);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`${r.data.number} started`, { description: s.name });
      router.push(`/inventory/counts/${r.data.id}`);
    });
  }

  function run(task: () => Promise<{ ok: boolean; error?: string }>, done: string) {
    start(async () => {
      const r = await task();
      if (!r.ok) return void toast.error(r.error ?? "That didn't work.");
      toast.success(done);
      router.refresh();
    });
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <p className="flex-1 text-sm font-medium text-ink">
          <CalendarClock className="mr-1.5 inline size-4 text-ink-3" aria-hidden />
          Cycle count schedules
        </p>
        {may.manage && !adding && (
          <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setAdding(true)}>
            Schedule a count
          </Button>
        )}
      </div>
      {schedules.length === 0 && !adding && (
        <p className="mt-1 text-meta text-ink-3">
          None yet. Schedule counts per warehouse or category (every week, month, quarter…) so stock is counted a little at a time instead of all at once.
        </p>
      )}
      {schedules.length > 0 && (
        <ul className="mt-2 divide-y divide-rule">
          {schedules.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-3 py-2">
              <span className="min-w-0 flex-1">
                <span className={`block text-sm font-semibold ${s.isActive ? "text-ink" : "text-ink-3 line-through"}`}>{s.name}</span>
                <span className="block text-meta text-ink-3">
                  {s.warehouse.name}
                  {s.category && ` · ${s.category.name}`} · {every(s.everyDays)} · next {s.nextLabel}
                  {s.lastLabel && ` · last counted ${s.lastLabel}`}
                </span>
              </span>
              {s.due && (
                <span className={`rounded-full px-2 py-0.5 text-meta ${s.overdueDays > 0 ? "bg-danger-tint text-danger" : "bg-promo-tint text-ink"}`}>
                  {s.overdueDays > 0 ? `Overdue ${s.overdueDays} ${s.overdueDays === 1 ? "day" : "days"}` : "Due today"}
                </span>
              )}
              {s.openCount && (
                <Link href={`/inventory/counts/${s.openCount.id}`} className="text-meta font-semibold text-hema hover:underline">
                  {s.openCount.number} open
                </Link>
              )}
              {may.create && s.isActive && !s.openCount && (
                <Button size="sm" variant={s.due ? "primary" : "quiet"} icon={<Play className="size-4" aria-hidden />} disabled={busy} onClick={() => begin(s)}>
                  {s.due ? "Start count" : "Start early"}
                </Button>
              )}
              {may.manage && (
                <>
                  <Button size="sm" variant="quiet" disabled={busy} onClick={() => run(() => saveCountSchedule(s.id, { isActive: !s.isActive }), s.isActive ? `${s.name} paused` : `${s.name} resumed`)}>
                    {s.isActive ? "Pause" : "Resume"}
                  </Button>
                  <button
                    suppressHydrationWarning
                    type="button"
                    title={`Delete ${s.name}`}
                    disabled={busy}
                    onClick={() => run(() => deleteCountSchedule(s.id), `${s.name} deleted`)}
                    className="rounded-md p-1.5 text-ink-3 hover:bg-sheet hover:text-danger"
                  >
                    <Trash2 className="size-4" aria-hidden />
                    <span className="sr-only">Delete {s.name}</span>
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {adding && (
        <form noValidate onSubmit={(e) => (e.preventDefault(), add())} className="mt-3 border-t border-rule pt-3">
          <div className="grid gap-4 sm:grid-cols-5">
            <Field label="Name" error={fields.name} className="sm:col-span-2">
              {(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={120} placeholder="Manila, medicines, monthly" autoFocus />}
            </Field>
            <Field label="Warehouse" error={fields.warehouseId}>
              {(p) => (
                <Select {...p} value={form.warehouseId} onChange={(e) => setForm({ ...form, warehouseId: e.target.value })}>
                  {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </Select>
              )}
            </Field>
            <Field label="Category" optional error={fields.categoryId}>
              {(p) => (
                <Select {...p} value={form.categoryId} onChange={(e) => setForm({ ...form, categoryId: e.target.value })}>
                  <option value="">All categories</option>
                  {reference.categories.map((c) => <option key={c.id} value={c.id}>{c.path}</option>)}
                </Select>
              )}
            </Field>
            <Field label="How often" error={fields.everyDays}>
              {(p) => (
                <Select {...p} value={form.everyDays} onChange={(e) => setForm({ ...form, everyDays: e.target.value })}>
                  {EVERY.map((e) => <option key={e.days} value={String(e.days)}>{e.label}</option>)}
                </Select>
              )}
            </Field>
            <Field label="First due" optional error={fields.nextOn} hint="Today when left empty.">
              {(p) => <Input {...p} type="date" value={form.nextOn} onChange={(e) => setForm({ ...form, nextOn: e.target.value })} />}
            </Field>
          </div>
          <FormError message={error} />
          <div className="mt-3 flex gap-2">
            <Button type="submit" size="sm" variant="primary" loading={busy}>Save schedule</Button>
            <Button size="sm" variant="quiet" disabled={busy} onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        </form>
      )}
    </div>
  );
}
