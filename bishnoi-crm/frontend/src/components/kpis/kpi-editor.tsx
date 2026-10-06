"use client";

import { ArrowDown, ArrowUp, Pencil, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Choice, Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import type { KpiCatalogue, KpiDef, KpiUnit } from "@/src/platform/lib/types";
import { deleteKpi, orderKpis, saveKpi, type KpiInput } from "../../actions/kpis";
import { FILTER_WORDS, UNIT_LABELS, words } from "./words";

type Product = { id: string; name: string };

/** Settings → KPIs: the list, in the order screens show them, each editable in place; and a new one. */
export function KpiEditor({ catalogue, products }: { catalogue: KpiCatalogue; products: Product[] }) {
  const router = useRouter();
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [pending, start] = useTransition();
  const items = catalogue.items;

  function move(i: number, by: -1 | 1) {
    const ids = items.map((k) => k.id);
    [ids[i], ids[i + by]] = [ids[i + by], ids[i]];
    start(async () => {
      const r = await orderKpis(ids);
      if (!r.ok) toast.error(r.error);
      router.refresh();
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        {editing !== "new" && (
          <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
            New KPI
          </Button>
        )}
      </div>
      {editing === "new" && (
        <Sheet className="px-5 py-4">
          <KpiForm catalogue={catalogue} products={products} kpi={null} onDone={() => setEditing(null)} />
        </Sheet>
      )}
      <Sheet>
        <ul className="divide-y divide-rule">
          {items.map((k, i) => (
            <li key={k.id} className="px-5 py-3">
              {editing === k.id ? (
                <KpiForm catalogue={catalogue} products={products} kpi={k} onDone={() => setEditing(null)} />
              ) : (
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
                      <span className={`font-semibold ${k.isActive ? "text-ink" : "text-ink-3 line-through"}`}>{k.name}</span>
                      {k.builtIn && <span className="text-meta text-ink-3">Built in</span>}
                      {!k.isActive && <span className="text-meta text-ink-3">Switched off</span>}
                    </p>
                    <p className="text-meta text-ink-2">
                      {k.measureLabel}
                      {k.filterLabel ? `: ${k.filterLabel}` : ""} · {UNIT_LABELS[k.unit].toLowerCase()} · {k.better === "higher" ? "higher is better" : "lower is better"} · on target from{" "}
                      {k.greenAt}%, slightly behind from {k.amberAt}%
                    </p>
                    <p className="text-meta text-ink-3">For {k.roles.length ? k.roles.map((r) => r.name).join(", ") : "everyone"}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-0.5">
                    <button type="button" onClick={() => move(i, -1)} disabled={i === 0 || pending} className="rounded-[14px] p-1.5 text-ink-3 hover:bg-bench disabled:opacity-30" aria-label={`Move ${k.name} up`}>
                      <ArrowUp className="size-4" aria-hidden />
                    </button>
                    <button type="button" onClick={() => move(i, 1)} disabled={i === items.length - 1 || pending} className="rounded-[14px] p-1.5 text-ink-3 hover:bg-bench disabled:opacity-30" aria-label={`Move ${k.name} down`}>
                      <ArrowDown className="size-4" aria-hidden />
                    </button>
                    <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setEditing(k.id)}>
                      Edit
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      </Sheet>
    </div>
  );
}

function KpiForm({ catalogue, products, kpi, onDone }: { catalogue: KpiCatalogue; products: Product[]; kpi: KpiDef | null; onDone: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [name, setName] = useState(kpi?.name ?? "");
  const [description, setDescription] = useState(kpi?.description ?? "");
  const [measure, setMeasure] = useState(kpi?.measure ?? catalogue.measures[0]?.key ?? "manual");
  const [filter, setFilter] = useState(Object.values(kpi?.filters ?? {})[0] ?? "");
  const [unit, setUnit] = useState<KpiUnit>(kpi?.unit ?? "count");
  const [better, setBetter] = useState<"higher" | "lower">(kpi?.better ?? "higher");
  const [roles, setRoles] = useState<string[]>(kpi?.roles.map((r) => r.id) ?? []);
  const [greenAt, setGreenAt] = useState(String(kpi?.greenAt ?? 100));
  const [amberAt, setAmberAt] = useState(String(kpi?.amberAt ?? 80));
  const [active, setActive] = useState(kpi?.isActive ?? true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const picked = catalogue.measures.find((m) => m.key === measure);
  const takes = picked?.filter ?? null;
  const fixed = kpi?.builtIn ?? false;

  function submit() {
    const g = Number(greenAt);
    const a = Number(amberAt);
    if (!Number.isInteger(g) || g < 1 || !Number.isInteger(a) || a < 0) {
      setFields({ greenAt: "Whole percentages of the target, like 100 and 80." });
      return;
    }
    const input: KpiInput = {
      name: name.trim(),
      description: description.trim() || null,
      measure,
      filters: takes && filter ? { [takes]: filter } : {},
      unit: picked ? picked.unit : unit,
      better,
      roles,
      greenAt: g,
      amberAt: a,
      isActive: active,
    };
    const change: Partial<KpiInput> = fixed ? { ...input, measure: undefined, filters: undefined } : input;
    start(async () => {
      const r = await saveKpi(kpi?.id ?? null, change);
      if (!r.ok) {
        setFields(r.fields ?? {});
        setError(r.fields ? null : r.error);
        return;
      }
      toast.success(kpi ? "KPI saved" : `${r.data.name} added`);
      router.refresh();
      onDone();
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" error={fields.name}>
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="e.g. Calls made" />}
        </Field>
        <Field label="What it means" optional error={fields.description}>
          {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} placeholder="Shown next to it" />}
        </Field>
        <Field label="What it measures" error={fields.measure} hint={fixed ? "A built-in KPI keeps what it measures." : picked?.about ?? "Typed in each month under Targets."}>
          {(p) => (
            <Select
              {...p}
              value={measure}
              disabled={fixed}
              onChange={(e) => {
                setMeasure(e.target.value);
                setFilter("");
              }}
            >
              {catalogue.measures.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
              <option value="manual">Entered by hand</option>
            </Select>
          )}
        </Field>
        {takes ? (
          <Field label={FILTER_WORDS[takes]} optional error={fields.filters}>
            {(p) => (
              <Select {...p} value={filter} disabled={fixed} onChange={(e) => setFilter(e.target.value)}>
                <option value="">All</option>
                {takes === "productId"
                  ? products.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.name}
                      </option>
                    ))
                  : (catalogue.filterChoices[takes] ?? []).map((o) => (
                      <option key={o} value={o}>
                        {words(o)}
                      </option>
                    ))}
              </Select>
            )}
          </Field>
        ) : measure === "manual" ? (
          <Field label="Entered as" error={fields.unit}>
            {(p) => (
              <Select {...p} value={unit} onChange={(e) => setUnit(e.target.value as KpiUnit)}>
                {(Object.keys(UNIT_LABELS) as KpiUnit[]).map((u) => (
                  <option key={u} value={u}>
                    {UNIT_LABELS[u]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        ) : (
          <div />
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-[auto_12rem_12rem]">
        <Choice<"higher" | "lower">
          name={`better-${kpi?.id ?? "new"}`}
          legend="Better when it's"
          value={better}
          onChange={setBetter}
          options={[
            { value: "higher", label: "Higher" },
            { value: "lower", label: "Lower" },
          ]}
        />
        <Field label="On target from (% of target)" error={fields.greenAt}>
          {(p) => <Input {...p} inputMode="numeric" value={greenAt} onChange={(e) => setGreenAt(e.target.value)} />}
        </Field>
        <Field label="Slightly behind from (%)" error={fields.amberAt} hint="Below this: behind.">
          {(p) => <Input {...p} inputMode="numeric" value={amberAt} onChange={(e) => setAmberAt(e.target.value)} />}
        </Field>
      </div>
      <fieldset>
        <legend className="mb-1.5 text-meta font-medium text-ink-2">Who it&apos;s for {fields.roles && <span className="text-danger">· {fields.roles}</span>}</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {catalogue.roles.map((r) => (
            <label key={r.id} className="inline-flex items-center gap-1.5 text-sm">
              <input type="checkbox" className="accent-hema" checked={roles.includes(r.id)} onChange={(e) => setRoles(e.target.checked ? [...roles, r.id] : roles.filter((x) => x !== r.id))} />
              {r.name}
            </label>
          ))}
        </div>
        <p className="mt-1 text-meta text-ink-3">None ticked: everyone.</p>
      </fieldset>
      {kpi && (
        <label className="inline-flex items-center gap-1.5 text-sm">
          <input type="checkbox" className="accent-hema" checked={active} onChange={(e) => setActive(e.target.checked)} />
          In use (switched off, it&apos;s kept but not shown or targeted)
        </label>
      )}
      <FormError message={error} />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {kpi ? "Save" : "Add KPI"}
        </Button>
        <Button variant="quiet" onClick={onDone}>
          Cancel
        </Button>
        {kpi && !kpi.builtIn && (
          <span className="ml-auto">
            <ConfirmButton
              label="Delete"
              triggerVariant="quiet"
              triggerSize="sm"
              title={`Delete ${kpi.name}?`}
              body="Its targets and any results entered by hand go with it. To keep them, switch it off instead."
              confirmLabel="Delete"
              onConfirm={async () => {
                const r = await deleteKpi(kpi.id);
                if (!r.ok) {
                  toast.error(r.error);
                  return false;
                }
                toast.success(`${kpi.name} deleted`);
                router.refresh();
                onDone();
              }}
            />
          </span>
        )}
      </div>
    </form>
  );
}
