"use client";

import { ChevronRight, Plus } from "lucide-react";
import { useEffect, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { createRole, deleteRole, savePermissions, updateRole } from "../actions/admin";
import { ACTION_LABELS } from "@/src/platform/lib/labels";
import type { RolesPayload } from "@/src/platform/lib/types";
import { PickList, SaveBar } from "@/src/platform/ui/pick-list";

const SETTINGS = "settings";
const ORDERS = "orders";
type Grants = Record<string, string[]>;

function sameGrants(a: Grants, b: Grants) {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  return [...keys].every((k) => [...(a[k] ?? [])].sort().join() === [...(b[k] ?? [])].sort().join());
}

export function RolesEditor({ data }: { data: RolesPayload }) {
  const [selected, setSelected] = useState(data.roles[0]?.key ?? "");
  const [drafts, setDrafts] = useState<Record<string, Grants>>({});
  const [saving, startSave] = useTransition();
  const role = data.roles.find((r) => r.key === selected) ?? data.roles[0];
  const saved = data.permissions[role?.key] ?? {};
  const grants = drafts[role?.key] ?? saved;
  const dirty = role && drafts[role.key] && !sameGrants(drafts[role.key], saved);

  function toggle(modules: string[], action: string, on: boolean) {
    const next = { ...grants };
    for (const key of modules) {
      const current = new Set(grants[key] ?? []);
      if (key === SETTINGS) {
        if (on) current.add(action);
        else current.delete(action);
      } else if (action === "view" && !on) {
        current.clear(); // can't add, edit or delete what you can't see
      } else {
        if (on) current.add(action);
        else current.delete(action);
        if (on) current.add("view");
      }
      next[key] = [...current];
    }
    setDrafts({ ...drafts, [role.key]: next });
  }

  function discard() {
    const next = { ...drafts };
    delete next[role.key];
    setDrafts(next);
  }

  function save() {
    startSave(async () => {
      const result = await savePermissions({ [role.key]: grants });
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      discard();
      toast.success(`${role.name} permissions saved`, { description: "People with this role get the change on their next click." });
    });
  }

  const sales = data.modules.filter((m) => m.kind === "crm");
  const departments = data.modules.filter((m) => m.kind === "department" && m.built);
  const unbuilt = data.modules.filter((m) => m.kind === "department" && !m.built);
  const orders = data.modules.some((m) => m.key === ORDERS);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
        <PickList
          title="Roles"
          icon="roles"
          items={data.roles.map((r) => ({
            key: r.key,
            label: r.name,
            detail: r.assignmentCount === 1 ? "1 assignment" : `${r.assignmentCount} assignments`,
            unsaved: Boolean(drafts[r.key] && !sameGrants(drafts[r.key], data.permissions[r.key] ?? {})),
          }))}
          selected={role?.key ?? ""}
          onSelect={setSelected}
          footer={<NewRole onCreated={(key) => setSelected(key)} />}
        />

        {/* The selected role's row of the matrix */}
        {role && (
          <Sheet className="px-5 pt-4 pb-5">
            <RoleDetails key={role.key} role={role} />
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[26rem] text-sm">
                <thead>
                  <tr className="border-b border-rule text-caps text-ink-3 uppercase">
                    <th scope="col" className="py-2 pr-3 text-left font-semibold">Module</th>
                    {data.actions.map((a) => (
                      <th key={a} scope="col" className="w-16 px-1 py-2 text-center font-semibold">
                        {ACTION_LABELS[a]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <SalesRows key={role.key} role={role.name} modules={sales} actions={data.actions} grants={grants} toggle={toggle} />
                <ModuleRows label="Departments" role={role.name} modules={departments} actions={data.actions} grants={grants} toggle={toggle} />
                {unbuilt.length > 0 && (
                  <UnbuiltRows key={`unbuilt-${role.key}`} role={role.name} modules={unbuilt} actions={data.actions} grants={grants} toggle={toggle} />
                )}
                <tbody>
                  <tr>
                    <th colSpan={1 + data.actions.length} scope="colgroup" className="pt-4 pb-1 text-left text-meta font-semibold text-ink-2">
                      Admin
                    </th>
                  </tr>
                  {/* Two keys, not one: running the company and keeping it
                      working are different jobs, and the second is the smaller.
                      Whoever holds it can put an account back, and an account is
                      a way in — so it says so, here, where it is given out. */}
                  {data.settingsActions.map((s) => (
                    <tr key={s.action} className="border-t border-rule">
                      <th scope="row" className="py-2 pr-3 text-left font-normal">
                        {s.label} <span className="block text-meta text-ink-3">{s.hint}</span>
                      </th>
                      <td className="px-1 py-2 text-center" colSpan={data.actions.length}>
                        <label className="inline-flex items-center gap-2 text-meta text-ink-2">
                          <input
                            type="checkbox"
                            checked={(grants[SETTINGS] ?? []).includes(s.action)}
                            onChange={(e) => toggle([SETTINGS], s.action, e.target.checked)}
                            className="size-4 accent-hema"
                          />
                          Yes
                        </label>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {orders && <OrderSteps role={role.name} steps={data.orderSteps} grants={grants} toggle={toggle} />}
            <p className="mt-3 text-meta text-ink-3">
              A role only works where someone is assigned it. Where they&apos;re assigned (which module, division and team) is set on
              each person&apos;s page.
            </p>
            {dirty && <SaveBar what={`Unsaved changes to ${role.name}`} saving={saving} onSave={save} onDiscard={discard} />}
          </Sheet>
        )}
      </div>

      <Overview data={data} />
    </div>
  );
}

type Module = RolesPayload["modules"][number];
type RowsProps = {
  role: string;
  modules: Module[];
  actions: RolesPayload["actions"];
  grants: Grants;
  toggle: (modules: string[], action: string, on: boolean) => void;
};

/** A tick that can also say "some of them" (the sales divisions don't all agree). */
function TriBox({ state, label, onChange }: { state: "all" | "some" | "none"; label: string; onChange: (on: boolean) => void }) {
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (box.current) box.current.indeterminate = state === "some";
  }, [state]);
  return (
    <input
      ref={box}
      type="checkbox"
      aria-label={label}
      checked={state === "all"}
      onChange={() => onChange(state !== "all")}
      className="size-4 accent-hema"
    />
  );
}

function Cell({ role, module, action, grants, toggle }: { role: string; module: Module; action: string; grants: Grants; toggle: RowsProps["toggle"] }) {
  // Reports (team and per-rep figures) exist for sales modules only, for now.
  if (action === "report" && module.kind !== "crm") {
    return (
      <span className="text-ink-3" aria-hidden>
        —
      </span>
    );
  }
  return (
    <input
      type="checkbox"
      aria-label={`${role}: ${ACTION_LABELS[action as keyof typeof ACTION_LABELS]} in ${module.name}`}
      checked={(grants[module.key] ?? []).includes(action)}
      onChange={(e) => toggle([module.key], action, e.target.checked)}
      className="size-4 accent-hema"
    />
  );
}

function ModuleRows({ label, role, modules, actions, grants, toggle }: RowsProps & { label: string }) {
  if (!modules.length) return null;
  return (
    <tbody className="divide-y divide-rule">
      <tr>
        <th colSpan={1 + actions.length} scope="colgroup" className="pt-4 pb-1 text-left text-meta font-semibold text-ink-2">
          {label}
        </th>
      </tr>
      {modules.map((m) => (
        <tr key={m.key}>
          <th scope="row" className="py-2 pr-3 text-left font-normal">
            {m.name}
          </th>
          {actions.map((a) => (
            <td key={a} className="px-1 py-2 text-center">
              <Cell role={role} module={m} action={a} grants={grants} toggle={toggle} />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}

/**
 * The six sales divisions usually get the same permissions, so they're one row
 * that sets all of them. "Per division" opens a row each; it starts open when
 * they already differ, so a difference is never hidden.
 */
function SalesRows({ role, modules, actions, grants, toggle }: RowsProps) {
  const key = (m: Module) => [...(grants[m.key] ?? [])].sort().join();
  const alike = new Set(modules.map(key)).size <= 1;
  const [open, setOpen] = useState(!alike);
  const keys = modules.map((m) => m.key);
  const state = (a: string) => {
    const n = modules.filter((m) => (grants[m.key] ?? []).includes(a)).length;
    return n === 0 ? "none" : n === modules.length ? "all" : "some";
  };
  return (
    <tbody className="divide-y divide-rule">
      <tr>
        <th colSpan={1 + actions.length} scope="colgroup" className="pt-4 pb-1 text-left text-meta font-semibold text-ink-2">
          Sales
        </th>
      </tr>
      <tr>
        <th scope="row" className="py-2 pr-3 text-left font-normal">
          <span className="flex flex-wrap items-center gap-x-3">
            All {modules.length} sales divisions
            <button
              type="button"
              onClick={() => setOpen(!open)}
              aria-expanded={open}
              className="inline-flex items-center gap-1 text-meta font-semibold text-hema hover:underline"
            >
              <ChevronRight aria-hidden className={`size-3.5 transition-transform ${open ? "rotate-90" : ""}`} />
              Per division
            </button>
            {!alike && !open && <span className="text-meta text-ink-3">they differ</span>}
          </span>
        </th>
        {actions.map((a) => (
          <td key={a} className="px-1 py-2 text-center">
            <TriBox state={state(a)} label={`${role}: ${ACTION_LABELS[a]} in every sales division`} onChange={(on) => toggle(keys, a, on)} />
          </td>
        ))}
      </tr>
      {open &&
        modules.map((m) => (
          <tr key={m.key} className="bg-bench/30">
            <th scope="row" className="py-2 pr-3 pl-5 text-left font-normal text-ink-2">
              {m.name}
            </th>
            {actions.map((a) => (
              <td key={a} className="px-1 py-2 text-center">
                <Cell role={role} module={m} action={a} grants={grants} toggle={toggle} />
              </td>
            ))}
          </tr>
        ))}
    </tbody>
  );
}

/** Modules that aren't built yet stay out of the way until asked for, unless this role already has something there. */
function UnbuiltRows({ role, modules, actions, grants, toggle }: RowsProps) {
  const granted = modules.some((m) => (grants[m.key] ?? []).length > 0);
  const [open, setOpen] = useState(granted);
  if (open) return <ModuleRows label="Not built yet" role={role} modules={modules} actions={actions} grants={grants} toggle={toggle} />;
  return (
    <tbody>
      <tr>
        <td colSpan={1 + actions.length} className="pt-3">
          <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-1 text-meta font-semibold text-hema hover:underline">
            <ChevronRight aria-hidden className="size-3.5" />
            {modules.length} modules not built yet
          </button>
          <span className="ml-2 text-meta text-ink-3">{modules.map((m) => m.name).join(", ")}</span>
        </td>
      </tr>
    </tbody>
  );
}

/**
 * The order steps: taken in the Orders app, set here. Grouped by who usually
 * takes them, so a role's job reads at a glance (raise and edit, approve, pay,
 * send out, clean up).
 */
function OrderSteps({ role, steps, grants, toggle }: {
  role: string;
  steps: RolesPayload["orderSteps"];
  grants: Grants;
  toggle: RowsProps["toggle"];
}) {
  const granted = new Set(grants[ORDERS] ?? []);
  return (
    <section aria-labelledby="order-steps" className="mt-5 border-t border-rule pt-4">
      <h3 id="order-steps" className="text-sm font-semibold">
        Orders <span className="font-normal text-ink-3">· steps taken in the Orders app</span>
      </h3>
      <p className="mt-0.5 text-meta text-ink-3">
        Someone given this role in a sales team takes these steps for that team&apos;s orders. Given it for Orders itself, they take them
        in every division.
      </p>
      <div className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(10.5rem,1fr))] gap-x-5 gap-y-4">
        {steps.map((group) => (
          <div key={group.group} role="group" aria-label={group.group}>
            <p className="text-caps text-ink-3 uppercase">{group.group}</p>
            <div className="mt-1">
              {group.steps.map((step) => (
                <label key={step.action} className="flex min-h-9 cursor-pointer items-center gap-2.5 rounded-[3px] px-1 text-sm hover:bg-bench/40">
                  <input
                    type="checkbox"
                    aria-label={`${role}: ${step.label} (orders)`}
                    checked={granted.has(step.action)}
                    onChange={(e) => toggle([ORDERS], step.action, e.target.checked)}
                    className="size-4 shrink-0 accent-hema"
                  />
                  {step.label}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RoleDetails({ role }: { role: RolesPayload["roles"][number] }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(role.name);
  const [description, setDescription] = useState(role.description);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  if (editing) {
    return (
      <form
        noValidate
        className="animate-reshape space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          start(async () => {
            const result = await updateRole(role.key, { name: name.trim(), description: description.trim() });
            if (!result.ok) return setError(result.error);
            toast.success("Role updated");
            setEditing(false);
          });
        }}
      >
        <Field label="Role name">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoFocus />}</Field>
        <Field label="What it's for" optional>
          {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />}
        </Field>
        <FormError message={error} />
        <div className="flex gap-2">
          <Button type="submit" size="sm" variant="primary" loading={pending}>
            Save
          </Button>
          <Button size="sm" variant="quiet" onClick={() => setEditing(false)} disabled={pending}>
            Cancel
          </Button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-heading">{role.name}</h2>
        {role.description && <p className="text-meta text-ink-2">{role.description}</p>}
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={() => setEditing(true)}>
          Rename
        </Button>
        <ConfirmButton
          label="Delete"
          triggerSize="sm"
          disabled={role.assignmentCount > 0}
          title={`Delete the ${role.name} role?`}
          body="Its permissions go with it. This can't be undone."
          confirmLabel="Delete role"
          onConfirm={async () => {
            const result = await deleteRole(role.key);
            if (!result.ok) {
              toast.error(result.error);
              return false;
            }
            toast.success(`${role.name} deleted`);
          }}
        />
      </div>
      {role.assignmentCount > 0 && (
        <p className="w-full text-meta text-ink-3">
          In use, so it can&apos;t be deleted. Move {role.assignmentCount === 1 ? "that person" : "those people"} to another role first.
        </p>
      )}
    </div>
  );
}

function NewRole({ onCreated }: { onCreated: (key: string) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <Button size="sm" variant="quiet" className="mt-2" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        New role
      </Button>
    );
  }
  return (
    <form
      noValidate
      className="animate-reshape mt-3 space-y-3 border-t border-rule px-2 pt-3"
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const result = await createRole({ name: name.trim(), description: "" });
          if (!result.ok) return setError(result.error);
          const created = (result.data as any)?.roles?.find((r: any) => r.name === name.trim());
          toast.success(`${name.trim()} created`, { description: "Tick what it can do, then save." });
          setOpen(false);
          setName("");
          if (created) onCreated(created.key);
        });
      }}

    >
      <Field label="Role name">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoFocus />}</Field>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" size="sm" variant="primary" loading={pending}>
          Create
        </Button>
        <Button size="sm" variant="quiet" onClick={() => setOpen(false)} disabled={pending}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** The whole matrix at once, modules down and roles across: folded away until someone wants to compare. */
function Overview({ data }: { data: RolesPayload }) {
  const letters = (grants: string[] | undefined) =>
    data.actions.filter((a) => grants?.includes(a)).map((a) => ACTION_LABELS[a][0]).join(" ");
  return (
    <Sheet as="div">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4">
          <span>
            <span className="font-semibold">Compare every role</span>
            <span className="ml-2 text-meta text-ink-3">every module, every role, side by side</span>
          </span>
          <ChevronRight aria-hidden className="size-4 shrink-0 text-ink-3 transition-transform group-open:rotate-90" />
        </summary>
        <div className="border-t border-rule px-5 pt-3 pb-4">
          <p className="text-meta text-ink-3">V view · A add · E edit · D delete · R reports · P prices. Saved permissions only.</p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-meta text-ink-3">
                  <th scope="col" className="py-2 pr-3 text-caps uppercase">Module</th>
                  {data.roles.map((r) => (
                    <th key={r.key} scope="col" className="px-2 py-2 font-semibold">
                      {r.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {data.modules.map((m) => (
                  <tr key={m.key}>
                    <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                      {m.name}
                    </th>
                    {data.roles.map((r) => {
                      const grants = data.permissions[r.key]?.[m.key];
                      // Order steps don't fit the letters; how many a role takes says enough here.
                      const shown = m.kind === "app" ? (grants?.length ? `${grants.length} steps` : "") : letters(grants);
                      return (
                        <td key={r.key} className="px-2 py-1.5 font-mono text-meta text-ink-2">
                          {shown || <span className="text-ink-3">—</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                <tr>
                  <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                    Settings
                  </th>
                  {data.roles.map((r) => {
                    const held = data.settingsActions.filter((s) => data.permissions[r.key]?.[SETTINGS]?.includes(s.action));
                    return (
                      <td key={r.key} className="px-2 py-1.5 text-meta text-ink-2">
                        {held.length ? held.map((s) => s.label).join(" · ") : <span className="text-ink-3">—</span>}
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </Sheet>
  );
}
