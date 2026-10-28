"use client";

import { Modal } from "antd";
import { Building2, MapPin, Pencil, Plus, Power, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Banner } from "@/src/platform/ui/alert";
import { Button, IconButton } from "@/src/platform/ui/button";
import { Field, FormGrid, Input, SearchInput } from "@/src/platform/ui/field";
import { Combobox, Select } from "@/src/platform/ui/pickers";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { Tip } from "@/src/platform/ui/tip";
import { addBranch, addUnit, changeBranch, changeUnit, placePerson, type UnitInput } from "./actions";
import { KIND_LABEL, type OrgBranch, type OrgData, type OrgPerson, type OrgUnit, type UnitKind } from "./types";

// The company's org chart on the Platform (feature plan step 4, agreed 2026-10-28): one chart for
// the whole company, edited here only; every app reads it (the CRM's teams follow it, invoices are
// tagged by division). Each control sits beside what it changes.

/** "HOS › Field NCR 1": a unit with the units above it. */
function pathName(units: Map<string, OrgUnit>, id: string): string {
  const names: string[] = [];
  const seen = new Set<string>();
  let at = units.get(id);
  while (at && !seen.has(at.id)) {
    seen.add(at.id);
    names.unshift(at.name);
    at = at.parentId ? units.get(at.parentId) : undefined;
  }
  return names.join(" › ");
}

/** The unit and every unit under it (it can't be moved under any of them). */
function withBelow(units: OrgUnit[], id: string): Set<string> {
  const out = new Set([id]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const u of units) if (u.parentId && out.has(u.parentId) && !out.has(u.id)) (out.add(u.id), (grew = true));
  }
  return out;
}

export function OrganisationChart({ data }: { data: OrgData }) {
  const [onlyUnplaced, setOnlyUnplaced] = useState(false);
  return (
    <div className="space-y-4">
      {data.notPlaced > 0 && (
        <Banner
          tone="warn"
          action={
            <Button size="sm" onClick={() => (setOnlyUnplaced(true), document.getElementById("people")?.scrollIntoView({ behavior: "smooth" }))}>
              Show them
            </Button>
          }
        >
          {data.notPlaced} {data.notPlaced === 1 ? "person isn't" : "people aren't"} on the chart yet. Give each a main unit, so their sales and approvals count in the right place.
        </Banner>
      )}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <UnitTree data={data} />
        <Branches data={data} />
      </div>
      <People data={data} onlyUnplaced={onlyUnplaced} setOnlyUnplaced={setOnlyUnplaced} />
    </div>
  );
}

// ---- The chart ------------------------------------------------------------------------------------

function UnitTree({ data }: { data: OrgData }) {
  const [editing, setEditing] = useState<{ unit?: OrgUnit; parentId?: string | null } | null>(null);
  const active = data.units.filter((u) => u.isActive);
  const off = data.units.filter((u) => !u.isActive);
  const people = new Map(data.people.map((p) => [p.id, p.fullName]));
  const ids = new Set(active.map((u) => u.id));
  const under = (parent: string | null) => active.filter((u) => (parent === null ? !u.parentId || !ids.has(u.parentId) : u.parentId === parent));

  function rows(parent: string | null, depth: number): React.ReactNode {
    return under(parent).map((u) => (
      <div key={u.id}>
        <UnitRow unit={u} depth={depth} manager={u.managerId ? people.get(u.managerId) : undefined} onEdit={() => setEditing({ unit: u })} onAdd={() => setEditing({ parentId: u.id })} />
        {rows(u.id, depth + 1)}
      </div>
    ));
  }

  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle
        icon="teams"
        action={
          <Button size="sm" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing({ parentId: null })}>
            Add unit
          </Button>
        }
      >
        Org chart
      </SectionTitle>
      {active.length === 0 ? (
        <Empty icon="teams" title="No units yet">
          Add your divisions and departments, then the teams under them.
        </Empty>
      ) : (
        <div className="mt-2 divide-y divide-rule">{rows(null, 0)}</div>
      )}
      {off.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-meta text-ink-3">Switched off ({off.length})</summary>
          <ul className="mt-1 divide-y divide-rule">
            {off.map((u) => (
              <li key={u.id} className="flex items-center gap-2 py-2 text-ink-3">
                <span className="min-w-0 flex-1 truncate">{u.name}</span>
                <span className="text-meta">{KIND_LABEL[u.kind]}</span>
                <SwitchUnit unit={u} />
              </li>
            ))}
          </ul>
        </details>
      )}
      {editing && <UnitDialog data={data} unit={editing.unit} parentId={editing.parentId ?? null} onClose={() => setEditing(null)} />}
    </Sheet>
  );
}

function UnitRow({ unit, depth, manager, onEdit, onAdd }: { unit: OrgUnit; depth: number; manager?: string; onEdit: () => void; onAdd: () => void }) {
  return (
    <div className="flex items-center gap-3 py-2.5" style={{ paddingLeft: `${depth * 1.25}rem` }}>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 text-sm">
          <span className={depth === 0 ? "font-semibold text-ink" : "font-medium text-ink"}>{unit.name}</span>
          <span className="rounded-full bg-bench px-2 py-0.5 text-meta text-ink-3">{KIND_LABEL[unit.kind]}</span>
          <IconButton label={`Add a unit under ${unit.name}`} onClick={onAdd}>
            <Plus className="size-3.5" aria-hidden />
          </IconButton>
        </p>
        <p className="truncate text-meta text-ink-3">
          {manager ? `Headed by ${manager}` : "No head yet"}
          {unit.areas.length > 0 && (
            <Tip tip={unit.areas.join(", ")}>
              <span>
                {" · "}
                <MapPin className="inline size-3" aria-hidden /> {unit.areas.length} {unit.areas.length === 1 ? "area" : "areas"}
              </span>
            </Tip>
          )}
        </p>
      </div>
      <Tip tip="People whose main unit this is">
        <span className="inline-flex items-center gap-1 text-meta text-ink-2">
          <Users className="size-3.5" aria-hidden /> {unit.people}
        </span>
      </Tip>
      <RowMenu
        label={`Actions for ${unit.name}`}
        items={[
          { label: "Change", icon: <Pencil />, onSelect: onEdit },
          "divider",
          {
            label: "Switch off",
            icon: <Power />,
            danger: true,
            run: () => changeUnit(unit.id, { isActive: false }),
            confirm: `Switch ${unit.name} off? Nobody new is put in it; its history stays.`,
            done: `${unit.name} is switched off`,
          },
        ]}
      />
    </div>
  );
}

function SwitchUnit({ unit }: { unit: OrgUnit }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  return (
    <Button
      size="sm"
      loading={busy}
      onClick={() =>
        start(async () => {
          const r = await changeUnit(unit.id, { isActive: true });
          if (!r.ok) toast.error(r.error);
          else router.refresh();
        })
      }
    >
      Switch on
    </Button>
  );
}

function UnitDialog({ data, unit, parentId, onClose }: { data: OrgData; unit?: OrgUnit; parentId: string | null; onClose: () => void }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const units = useMemo(() => new Map(data.units.map((u) => [u.id, u])), [data.units]);
  const below = unit ? withBelow(data.units, unit.id) : new Set<string>();
  const [form, setForm] = useState<UnitInput>({
    kind: unit?.kind ?? (parentId ? "team" : "division"),
    name: unit?.name ?? "",
    parentId: unit ? unit.parentId : parentId,
    managerId: unit?.managerId ?? null,
    areas: unit?.areas ?? [],
  });

  function save() {
    start(async () => {
      const body = { ...form, name: form.name.trim() };
      const r = unit ? await changeUnit(unit.id, body) : await addUnit(body);
      if (!r.ok) {
        setErrors("fields" in r && r.fields ? r.fields : {});
        return void toast.error(r.error);
      }
      toast.success(unit ? "Saved" : `${body.name} added`);
      onClose();
      router.refresh();
    });
  }

  const parents = data.units.filter((u) => u.isActive && !below.has(u.id)).map((u) => ({ value: u.id, label: pathName(units, u.id) }));
  parents.sort((a, b) => a.label.localeCompare(b.label));
  return (
    <Modal open title={unit ? `Change ${unit.name}` : "Add unit"} onCancel={() => !busy && onClose()} onOk={save} okText={unit ? "Save" : "Add unit"} confirmLoading={busy} width={560} destroyOnHidden>
      <FormGrid className="pt-2">
        <Field label="Name" size="md" error={errors.name}>
          {(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus maxLength={120} placeholder="e.g. HOS" />}
        </Field>
        <Field label="Kind" size="md" error={errors.kind}>
          {(p) => (
            <Select {...p} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as UnitKind })}>
              {(Object.keys(KIND_LABEL) as UnitKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Under" size="md" optional error={errors.parentId} hint="Leave empty for the top of the chart.">
          {() => <Combobox allowClear placeholder="Top of the chart" options={parents} value={form.parentId ?? undefined} onChange={(v) => setForm({ ...form, parentId: (v as string | undefined) ?? null })} />}
        </Field>
        <Field label="Head" size="md" optional error={errors.managerId}>
          {() => (
            <Combobox
              allowClear
              placeholder="Choose a person"
              options={data.people.filter((p) => p.status === "active").map((p) => ({ value: p.id, label: p.fullName }))}
              value={form.managerId ?? undefined}
              onChange={(v) => setForm({ ...form, managerId: (v as string | undefined) ?? null })}
            />
          )}
        </Field>
        <Field label="Areas it covers" size="full" optional hint="Places such as Commonwealth or Cebu. Type one and press Enter.">
          {() => <Combobox mode="tags" placeholder="Add an area" value={form.areas} onChange={(v) => setForm({ ...form, areas: (v as string[]) ?? [] })} options={[]} />}
        </Field>
      </FormGrid>
    </Modal>
  );
}

// ---- Branches -------------------------------------------------------------------------------------

function Branches({ data }: { data: OrgData }) {
  const [editing, setEditing] = useState<OrgBranch | "new" | null>(null);
  const shown = [...data.branches].sort((a, b) => Number(b.isActive) - Number(a.isActive));
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle
        icon="companies"
        action={
          <Button size="sm" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
            Add branch
          </Button>
        }
      >
        Branches
      </SectionTitle>
      {shown.length === 0 ? (
        <Empty icon="companies" title="No branches yet">
          Add the places people work from, such as the main office.
        </Empty>
      ) : (
        <ul className="mt-2 divide-y divide-rule">
          {shown.map((b) => (
            <li key={b.id} className={`flex items-center gap-3 py-2.5 ${b.isActive ? "" : "text-ink-3"}`}>
              <Building2 className="size-4 shrink-0 text-ink-3" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className={`block truncate text-sm ${b.isActive ? "font-medium text-ink" : ""}`}>
                  {b.name}
                  {!b.isActive && <span className="ml-2 text-meta">Switched off</span>}
                </span>
                {b.address && <span className="block truncate text-meta text-ink-3">{b.address}</span>}
              </span>
              <Tip tip="People who work here">
                <span className="inline-flex items-center gap-1 text-meta text-ink-2">
                  <Users className="size-3.5" aria-hidden /> {b.people}
                </span>
              </Tip>
              <RowMenu
                label={`Actions for ${b.name}`}
                items={[
                  { label: "Change", icon: <Pencil />, onSelect: () => setEditing(b) },
                  "divider",
                  b.isActive
                    ? { label: "Switch off", icon: <Power />, danger: true, run: () => changeBranch(b.id, { isActive: false }), confirm: `Switch ${b.name} off?`, done: `${b.name} is switched off` }
                    : { label: "Switch on", icon: <Power />, run: () => changeBranch(b.id, { isActive: true }), done: `${b.name} is switched on` },
                ]}
              />
            </li>
          ))}
        </ul>
      )}
      {editing && <BranchDialog branch={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} />}
    </Sheet>
  );
}

function BranchDialog({ branch, onClose }: { branch?: OrgBranch; onClose: () => void }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [form, setForm] = useState({ name: branch?.name ?? "", address: branch?.address ?? "" });

  function save() {
    start(async () => {
      const body = { name: form.name.trim(), address: form.address.trim() || null };
      const r = branch ? await changeBranch(branch.id, body) : await addBranch(body);
      if (!r.ok) {
        setErrors("fields" in r && r.fields ? r.fields : {});
        return void toast.error(r.error);
      }
      toast.success(branch ? "Saved" : `${body.name} added`);
      onClose();
      router.refresh();
    });
  }

  return (
    <Modal open title={branch ? `Change ${branch.name}` : "Add branch"} onCancel={() => !busy && onClose()} onOk={save} okText={branch ? "Save" : "Add branch"} confirmLoading={busy} width={480} destroyOnHidden>
      <FormGrid className="pt-2">
        <Field label="Name" size="full" error={errors.name}>
          {(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus maxLength={120} placeholder="e.g. Main office" />}
        </Field>
        <Field label="Address" size="full" optional error={errors.address}>
          {(p) => <Input {...p} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} maxLength={200} />}
        </Field>
      </FormGrid>
    </Modal>
  );
}

// ---- Where people sit -----------------------------------------------------------------------------

function People({ data, onlyUnplaced, setOnlyUnplaced }: { data: OrgData; onlyUnplaced: boolean; setOnlyUnplaced: (v: boolean) => void }) {
  const [query, setQuery] = useState("");
  const units = useMemo(() => new Map(data.units.map((u) => [u.id, u])), [data.units]);
  const unitOptions = useMemo(
    () => data.units.filter((u) => u.isActive).map((u) => ({ value: u.id, label: pathName(units, u.id) })).sort((a, b) => a.label.localeCompare(b.label)),
    [data.units, units],
  );
  const shown = data.people.filter((p) => {
    const q = query.trim().toLowerCase();
    return (!onlyUnplaced || (p.status === "active" && !p.mainUnitId)) && (!q || p.fullName.toLowerCase().includes(q) || p.email.toLowerCase().includes(q));
  });

  return (
    <Sheet className="px-5 pt-4 pb-2" id="people">
      <SectionTitle icon="people">Where people sit</SectionTitle>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <div className="w-full max-w-xs">
          <SearchInput placeholder="Find a person" allowClear value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-ink-2">
          <input suppressHydrationWarning type="checkbox" checked={onlyUnplaced} onChange={(e) => setOnlyUnplaced(e.target.checked)} />
          Only those not on the chart ({data.notPlaced})
        </label>
        <span className="ml-auto text-meta text-ink-3">
          {shown.length} of {data.people.length}
        </span>
      </div>
      {shown.length === 0 ? (
        <Empty icon="people" title="Nobody matches">
          Try another name or email.
        </Empty>
      ) : (
        <ul className="mt-3 divide-y divide-rule">
          {shown.map((p) => (
            <PersonRow key={p.id} person={p} unitOptions={unitOptions} branches={data.branches} />
          ))}
        </ul>
      )}
    </Sheet>
  );
}

function PersonRow({ person, unitOptions, branches }: { person: OrgPerson; unitOptions: { value: string; label: string }[]; branches: OrgBranch[] }) {
  const router = useRouter();
  const [saving, start] = useTransition();
  const [place, setPlace] = useState({ mainUnitId: person.mainUnitId, otherUnitIds: person.otherUnitIds, branchId: person.branchId });

  function save(next: typeof place) {
    setPlace(next);
    start(async () => {
      const r = await placePerson(person.id, next);
      if (!r.ok) {
        toast.error(r.error);
        setPlace({ mainUnitId: person.mainUnitId, otherUnitIds: person.otherUnitIds, branchId: person.branchId });
      } else router.refresh();
    });
  }

  return (
    <li className="grid gap-3 py-3 lg:grid-cols-[minmax(0,1fr)_16rem_minmax(0,1fr)_12rem] lg:items-center">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-ink">
          {person.fullName}
          {person.status !== "active" && <span className="ml-2 rounded-full bg-bench px-2 py-0.5 text-meta font-normal text-ink-3">Suspended</span>}
        </p>
        <p className="truncate text-meta text-ink-3">
          {person.email}
          {person.title ? ` · ${person.title}` : ""}
        </p>
      </div>
      <Combobox
        aria-label={`${person.fullName}'s main unit`}
        allowClear
        placeholder="Main unit"
        disabled={saving}
        options={unitOptions}
        value={place.mainUnitId ?? undefined}
        onChange={(v) => save({ ...place, mainUnitId: (v as string | undefined) ?? null })}
      />
      <Combobox
        aria-label={`${person.fullName}'s other units`}
        mode="multiple"
        placeholder="Other units"
        disabled={saving}
        options={unitOptions.filter((o) => o.value !== place.mainUnitId)}
        value={place.otherUnitIds}
        onChange={(v) => save({ ...place, otherUnitIds: (v as string[]) ?? [] })}
      />
      <Select aria-label={`${person.fullName}'s branch`} value={place.branchId ?? ""} disabled={saving} onChange={(e) => save({ ...place, branchId: e.target.value || null })}>
        <option value="">No branch</option>
        {branches
          .filter((b) => b.isActive || b.id === place.branchId)
          .map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
      </Select>
    </li>
  );
}
