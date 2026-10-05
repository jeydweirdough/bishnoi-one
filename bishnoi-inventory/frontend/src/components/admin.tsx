"use client";

import { KeyRound, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { PickList, SaveBar } from "@/src/platform/ui/pick-list";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { deleteRole, saveRole, saveUser, setUserPassword } from "../actions/inventory";
import type { AdminUsers, PermissionArea, RolesData } from "../lib/types";
import { useSave } from "./lines";

/** Everyone who can sign in here: their role, on or off, and a new password when they need one. */
export function UsersEditor({ data, meId, when }: { data: AdminUsers; meId: string; when: Record<string, string> }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [adding, setAdding] = useState(false);
  const { pending: saving, error, fields, save } = useSave();
  const [d, setD] = useState({ fullName: "", email: "", roleId: data.roles.find((r) => r.name === "Warehouse")?.id ?? data.roles[0]?.id ?? "", password: "" });

  function change(id: string, input: Record<string, unknown>, done: string) {
    start(async () => {
      const r = await saveUser(id, input);
      if (!r.ok) toast.error(r.error);
      else {
        toast.success(done);
        router.refresh();
      }
    });
  }

  return (
    <div className="space-y-5">
      {adding ? (
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="addRole">Add a person</SectionTitle>
          <form
            noValidate
            className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-4"
            onSubmit={(e) => {
              e.preventDefault();
              save(() => saveUser(null, { ...d, fullName: d.fullName.trim(), email: d.email.trim() }), () => {
                setAdding(false);
                setD({ ...d, fullName: "", email: "", password: "" });
                return { message: `${d.fullName.trim()} added` };
              });
            }}
          >
            <Field label="Full name" error={fields.fullName}>{(p) => <Input {...p} value={d.fullName} onChange={(e) => setD({ ...d, fullName: e.target.value })} autoFocus />}</Field>
            <Field label="Work email" error={fields.email}>{(p) => <Input {...p} type="email" value={d.email} onChange={(e) => setD({ ...d, email: e.target.value })} />}</Field>
            <Field label="Role" error={fields.roleId} hint={data.roles.find((r) => r.id === d.roleId)?.description ?? undefined}>
              {(p) => <Select {...p} value={d.roleId} onChange={(e) => setD({ ...d, roleId: e.target.value })}>{data.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>}
            </Field>
            <Field label="First password" error={fields.password} hint="At least 8 characters. Give it to them yourself.">
              {(p) => <Input {...p} type="password" autoComplete="new-password" value={d.password} onChange={(e) => setD({ ...d, password: e.target.value })} />}
            </Field>
            <div className="flex gap-2 sm:col-span-2 lg:col-span-4">
              <Button type="submit" variant="primary" loading={saving}>Add person</Button>
              <Button variant="quiet" onClick={() => setAdding(false)}>Cancel</Button>
            </div>
            {error && <div className="sm:col-span-2 lg:col-span-4"><FormError message={error} /></div>}
          </form>
        </Sheet>
      ) : (
        <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setAdding(true)}>Add a person</Button>
      )}

      <Sheet>
        <ul className="divide-y divide-rule">
          {data.items.map((u) => (
            <li key={u.id} className="grid gap-3 px-5 py-3 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-center">
              <span className="min-w-0 text-sm">
                <span className={`font-semibold ${u.isActive ? "" : "text-ink-3 line-through"}`}>{u.fullName}</span>
                {u.id === meId && <span className="ml-2 text-meta text-hema">You</span>}
                <span className="block text-meta text-ink-3">{u.email} · {u.lastSignInAt ? `last signed in ${when[u.id]}` : "never signed in"}{!u.isActive && " · switched off"}</span>
              </span>
              <Select aria-label={`${u.fullName}'s role`} value={u.role.id} disabled={pending} onChange={(e) => change(u.id, { roleId: e.target.value }, `${u.fullName} is now ${data.roles.find((r) => r.id === e.target.value)?.name}`)}>
                {data.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </Select>
              <span className="flex items-center gap-1 justify-self-end">
                <NewPassword id={u.id} name={u.fullName} />
                {u.id !== meId && (
                  <Button size="sm" variant="quiet" disabled={pending} onClick={() => change(u.id, { isActive: !u.isActive }, u.isActive ? `${u.fullName} switched off` : `${u.fullName} switched back on`)}>
                    {u.isActive ? "Switch off" : "Switch on"}
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      </Sheet>
    </div>
  );
}

function NewPassword({ id, name }: { id: string; name: string }) {
  const [password, setPassword] = useState("");
  return (
    <ConfirmButton
      label={<span className="sr-only">New password for {name}</span>}
      icon={<KeyRound className="size-4" aria-hidden />}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerTitle={`Set a new password for ${name}`}
      title={`A new password for ${name}`}
      body={
        <div className="space-y-2">
          <p>Their sessions end, and they sign in with this. Give it to them yourself.</p>
          <Input type="password" autoComplete="new-password" aria-label="New password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
      }
      confirmLabel="Set password"
      danger={false}
      onConfirm={async () => {
        const r = await setUserPassword(id, password);
        if (!r.ok) {
          toast.error(r.error);
          return false;
        }
        toast.success(`New password set for ${name}`);
        setPassword("");
        return true;
      }}
    />
  );
}

type RoleInput = { name: string; description: string | null; permissions: string[] };
const NEW = "__new";

/** Roles and what each allows, area by area. */
export function RolesEditor({ data }: { data: RolesData }) {
  const router = useRouter();
  const [selected, setSelected] = useState(data.roles[0]?.id ?? NEW);
  const [drafts, setDrafts] = useState<Record<string, RoleInput>>({});
  const [errors, setErrors] = useState<{ message: string | null; fields: Record<string, string> }>({ message: null, fields: {} });
  const [saving, start] = useTransition();
  const role = data.roles.find((r) => r.id === selected) ?? null;
  const saved: RoleInput = role ? { name: role.name, description: role.description, permissions: [...role.permissions].sort() } : { name: "", description: null, permissions: [] };
  const draft = drafts[selected] ?? saved;
  const same = (a: RoleInput, b: RoleInput) => a.name.trim() === b.name.trim() && (a.description ?? "").trim() === (b.description ?? "").trim() && a.permissions.join() === [...b.permissions].sort().join();
  const dirty = selected === NEW ? selected in drafts : !same(draft, saved);
  const locked = role?.isSystem ?? false;
  const edit = (change: Partial<RoleInput>) => setDrafts({ ...drafts, [selected]: { ...draft, ...change } });

  function pick(id: string) {
    setSelected(id);
    setErrors({ message: null, fields: {} });
  }

  function discard() {
    const next = { ...drafts };
    delete next[selected];
    setDrafts(next);
    if (selected === NEW) setSelected(data.roles[0]?.id ?? NEW);
  }

  function save() {
    start(async () => {
      const input = { ...draft, name: draft.name.trim(), description: draft.description?.trim() || null };
      const result = await saveRole(role?.id ?? null, input);
      if (!result.ok) return setErrors({ message: result.error, fields: result.fields ?? {} });
      const next = { ...drafts };
      delete next[selected];
      setDrafts(next);
      setSelected(result.data.id);
      toast.success(role ? `${input.name} saved` : `${input.name} added`, { description: role ? "People with this role get the change on their next click." : undefined });
      router.refresh();
    });
  }

  const items = [
    ...data.roles.map((r) => ({ key: r.id, label: r.name, detail: `${r.userCount} ${r.userCount === 1 ? "person" : "people"}`, unsaved: r.id in drafts && !same(drafts[r.id], { name: r.name, description: r.description, permissions: r.permissions }) })),
    ...(NEW in drafts || selected === NEW ? [{ key: NEW, label: draft.name.trim() || "New role", detail: "Not saved yet", unsaved: true }] : []),
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
      <PickList
        title="Roles"
        icon="roles"
        items={items}
        selected={selected}
        onSelect={pick}
        footer={<div className="mt-3 px-2"><Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => pick(NEW)} disabled={selected === NEW}>New role</Button></div>}
      />
      <div className="min-w-0 space-y-5">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle
            icon="roles"
            action={
              role && !locked && role.userCount === 0 ? (
                <ConfirmButton
                  label="Delete role"
                  title={`Delete ${role.name}?`}
                  body="Nobody has this role, so nothing else changes."
                  confirmLabel="Delete role"
                  triggerSize="sm"
                  triggerVariant="quiet"
                  onConfirm={async () => {
                    const r = await deleteRole(role.id);
                    if (!r.ok) {
                      toast.error(r.error);
                      return false;
                    }
                    toast.success(`${role.name} deleted`);
                    setSelected(data.roles.find((x) => x.id !== role.id)?.id ?? NEW);
                    router.refresh();
                    return true;
                  }}
                />
              ) : role && !locked ? (
                <span className="text-meta text-ink-3">In use by {role.userCount} {role.userCount === 1 ? "person" : "people"}</span>
              ) : null
            }
          >
            {role ? role.name : "New role"}
          </SectionTitle>
          {locked ? (
            <p className="mt-2 text-meta text-ink-2">The Administrator role always has every permission, including ones added later. It can&apos;t be changed or deleted, so there&apos;s always a way to fix access. To give someone less, make a new role.</p>
          ) : (
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <Field label="Name" error={errors.fields.name}>{(p) => <Input {...p} value={draft.name} onChange={(e) => edit({ name: e.target.value })} autoFocus={selected === NEW} />}</Field>
              <Field label="What it's for" optional error={errors.fields.description}>{(p) => <Textarea {...p} rows={1} value={draft.description ?? ""} onChange={(e) => edit({ description: e.target.value })} />}</Field>
            </div>
          )}
        </Sheet>
        <Permissions catalogue={data.catalogue} granted={draft.permissions} locked={locked} onChange={(permissions) => edit({ permissions })} />
        {!locked && dirty && (
          <SaveBar
            what={role ? <>Unsaved changes to <strong>{role.name}</strong></> : "A new role, not saved yet"}
            saving={saving}
            onSave={save}
            onDiscard={discard}
            saveLabel={role ? "Save changes" : "Add role"}
            error={<FormError message={errors.message} />}
          />
        )}
      </div>
    </div>
  );
}

function Permissions({ catalogue, granted, locked, onChange }: { catalogue: PermissionArea[]; granted: string[]; locked: boolean; onChange: (p: string[]) => void }) {
  const has = new Set(granted);
  const groups = [...new Set(catalogue.map((a) => a.group))];

  function toggle(area: PermissionArea, permission: string, on: boolean) {
    const next = new Set(has);
    const view = `${area.key}.view`;
    const hasView = area.actions.some((a) => a.permission === view);
    if (on) {
      next.add(permission);
      // Doing anything in an area starts with seeing it.
      if (hasView) next.add(view);
    } else {
      next.delete(permission);
      // Without seeing an area there's nothing in it to do.
      if (permission === view) for (const a of area.actions) next.delete(a.permission);
    }
    onChange([...next].sort());
  }

  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle icon="password">Permissions</SectionTitle>
      {groups.map((group) => (
        <div key={group} className="mt-4">
          <h3 className="text-caps text-ink-3 uppercase">{group}</h3>
          <ul className="mt-1 divide-y divide-rule">
            {catalogue.filter((a) => a.group === group).map((area) => (
              <li key={area.key} className="grid gap-2 py-2.5 md:grid-cols-[16rem_minmax(0,1fr)] md:items-center">
                <span className="text-sm text-ink">{area.name}</span>
                <div className="flex flex-wrap items-center gap-1.5">
                  {area.actions.map((a) => {
                    const on = has.has(a.permission);
                    return (
                      <label key={a.permission} className={`relative inline-flex items-center rounded-full border px-3 py-1 text-meta has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-hema ${on ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong bg-sheet text-ink-2"} ${locked ? "cursor-default" : "cursor-pointer hover:border-hema"}`}>
                        <input type="checkbox" className="sr-only" checked={on} disabled={locked} onChange={(e) => toggle(area, a.permission, e.target.checked)} />
                        {a.label}
                      </label>
                    );
                  })}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </Sheet>
  );
}
