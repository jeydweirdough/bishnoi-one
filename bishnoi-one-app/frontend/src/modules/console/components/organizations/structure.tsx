"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/console/platform/ui/button";
import { ConfirmButton } from "@/src/modules/console/platform/ui/confirm";
import { Field, FormError, FormGrid, Input } from "@/src/modules/console/platform/ui/field";
import { Empty, SectionTitle, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { Count } from "@/src/modules/console/components/marks";
import { addUnit, deleteUnit, updateUnit } from "@/src/modules/console/actions/organizations";
import type { Unit } from "@/src/modules/console/lib/types";
import { ICON_BUTTON, ICON_TRIGGER_DANGER } from "@/src/modules/console/components/organizations/record-tools";

const WORDS = {
  department: { one: "department", title: "Departments", empty: "No departments yet", place: "Location" },
  branch: { one: "branch", title: "Branches", empty: "No branches yet", place: "Location" },
} as const;

/** A company's departments and branches, each with its edit and delete beside its name. */
export function Structure({ companyId, companyName, units, canChange }: { companyId: string; companyName: string; units: Unit[]; canChange: boolean }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {(["department", "branch"] as const).map((kind) => (
        <UnitList key={kind} kind={kind} companyId={companyId} companyName={companyName} units={units.filter((u) => u.kind === kind)} canChange={canChange} />
      ))}
    </div>
  );
}

function UnitList({ kind, companyId, companyName, units, canChange }: { kind: Unit["kind"]; companyId: string; companyName: string; units: Unit[]; canChange: boolean }) {
  const w = WORDS[kind];
  const [adding, setAdding] = useState(false);
  return (
    <Sheet className="self-start">
      <div className="px-5 pt-4 pb-2">
        <SectionTitle
          icon={kind === "department" ? "teams" : "headquarters"}
          action={
            canChange &&
            !adding && (
              <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setAdding(true)}>
                Add a {w.one}
              </Button>
            )
          }
        >
          {w.title}
          <Count n={units.length} />
        </SectionTitle>
      </div>
      {units.length === 0 && !adding ? (
        <Empty title={w.empty} icon={kind === "department" ? "teams" : "headquarters"}>
          {canChange ? `Add ${companyName}'s ${w.title.toLowerCase()} with "Add a ${w.one}" above.` : "A Platform Admin can add them."}
        </Empty>
      ) : (
        <ul className="divide-y divide-rule border-t border-rule" role="list">
          {units.map((u) => (
            <UnitRow key={u.id} unit={u} companyId={companyId} canChange={canChange} />
          ))}
        </ul>
      )}
      {adding && <UnitForm kind={kind} companyId={companyId} onDone={() => setAdding(false)} />}
    </Sheet>
  );
}

function UnitRow({ unit, companyId, canChange }: { unit: Unit; companyId: string; canChange: boolean }) {
  const [editing, setEditing] = useState(false);
  const w = WORDS[unit.kind];
  if (editing) return <UnitForm kind={unit.kind} companyId={companyId} unit={unit} onDone={() => setEditing(false)} />;
  return (
    <li className="flex items-center gap-2 px-5 py-2.5">
      <span className="min-w-0">
        <span className="flex flex-wrap items-center gap-1">
          <span className="font-semibold text-ink">{unit.name}</span>
          {canChange && (
            <span className="flex items-center">
              <button suppressHydrationWarning type="button" className={ICON_BUTTON} title={`Edit ${w.one} ${unit.name}`} aria-label={`Edit ${w.one} ${unit.name}`} onClick={() => setEditing(true)}>
                <Pencil className="size-4" aria-hidden />
              </button>
              <ConfirmButton
                label={<span className="sr-only">Delete {w.one} {unit.name}</span>}
                icon={<Trash2 className="size-4" aria-hidden />}
                triggerTitle={`Delete ${w.one} ${unit.name}`}
                triggerVariant="quiet"
                triggerSize="sm"
                triggerClassName={ICON_TRIGGER_DANGER}
                title={`Delete the ${w.one} ${unit.name}?`}
                body={`It is removed from the company's structure. Its users stay at the company.`}
                confirmLabel={`Delete ${w.one}`}
                onConfirm={async () => {
                  const result = await deleteUnit(companyId, unit.id);
                  if (!result.ok) {
                    toast.error(result.error);
                    return false;
                  }
                  toast.success(`${unit.kind === "branch" ? "Branch" : "Department"} deleted`, { description: unit.name });
                }}
              />
            </span>
          )}
        </span>
        <span className="block text-meta text-ink-3">{unit.location || "No location given"}</span>
      </span>
    </li>
  );
}

function UnitForm({ kind, companyId, unit, onDone }: { kind: Unit["kind"]; companyId: string; unit?: Unit; onDone: () => void }) {
  const w = WORDS[kind];
  const [name, setName] = useState(unit?.name ?? "");
  const [location, setLocation] = useState(unit?.location ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pending, start] = useTransition();

  function submit() {
    start(async () => {
      const where = location.trim() || null;
      const result = unit
        ? await updateUnit(companyId, unit.id, { name: name.trim(), location: where })
        : await addUnit(companyId, { kind, name: name.trim(), location: where });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(unit ? "Saved" : `${kind === "branch" ? "Branch" : "Department"} added`, { description: name.trim() });
      onDone();
    });
  }

  const Tag = unit ? "li" : "div";
  return (
    <Tag className="border-t border-rule bg-bench/40 px-5 py-4 first:border-t-0">
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="space-y-4"
      >
        <FormGrid>
          <Field label={`${w.one === "branch" ? "Branch" : "Department"} name`} size="md" error={fields.name}>
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} autoFocus required />}
          </Field>
          <Field label={w.place} size="md" optional error={fields.location}>
            {(p) => <Input {...p} value={location} onChange={(e) => setLocation(e.target.value)} />}
          </Field>
        </FormGrid>
        <FormError message={error} />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" size="sm" variant="primary" loading={pending}>
            {unit ? "Save" : `Add ${w.one}`}
          </Button>
          <Button size="sm" variant="quiet" onClick={onDone} disabled={pending}>
            Cancel
          </Button>
        </div>
      </form>
    </Tag>
  );
}
