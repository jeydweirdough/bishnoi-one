"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { ConfirmButton } from "@/src/modules/finance/platform/ui/confirm";
import { Field, FormError, FormGrid, Input, Textarea } from "@/src/modules/finance/platform/ui/field";
import { PickList, SaveBar } from "@/src/modules/finance/platform/ui/pick-list";
import { SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { deleteRole, saveRole, saveUser } from "@/src/modules/finance/actions/admin";
import { removeUserSignature } from "@/src/modules/finance/signature/actions";
import type { AdminUsers, PermissionArea, RolesData } from "@/src/modules/finance/lib/types";


function useSave() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  function save<T>(run: () => Promise<{ ok: true; data: T } | { ok: false; error: string; fields?: Record<string, string> }>, done: (data: T) => { message: string; go?: string }) {
    start(async () => {
      const result = await run();
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      const next = done(result.data);
      toast.success(next.message);
      if (next.go) router.push(next.go);
      else router.refresh();
    });
  }

  return { pending, error, fields, save };
}

/** Everyone who can sign in to Finance: their role, on or off, and password reset. */
/**
 * Who opens this module, and the role each has here. Adding people, their role, password and
 * switching them off are done once for every module in Bishnoi One's People (R2, decided
 * 2026-10-26); this page keeps what is the module's own.
 */
export function UsersEditor({
  data,
  meId,
  when,
}: {
  data: AdminUsers;
  meId: string;
  when: Record<string, string>;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [adding, setAdding] = useState(false);
  const { pending: saving, error, fields, save } = useSave();
  const [d, setD] = useState({
    fullName: "",
    email: "",
    roleId: data.roles.find((r) => r.name === "Finance Staff")?.id ?? data.roles[0]?.id ?? "",
    password: "",
  });

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
      <Sheet>
        <ul className="divide-y divide-rule">
          {data.items.map((u) => (
            <li
              key={u.id}
              className="grid gap-3 px-5 py-3 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-center"
            >
              <span className="min-w-0 text-sm">
                <span className={`font-semibold ${u.isActive ? "" : "text-ink-3 line-through"}`}>
                  {u.fullName}
                </span>
                {u.id === meId && <span className="ml-2 text-meta text-hema font-semibold">You</span>}
                <span className="block text-meta text-ink-3">
                  {u.email} · {u.lastSignInAt ? `last signed in ${when[u.id]}` : "never signed in"}
                  {!u.isActive && " · inactive"}
                </span>
              </span>
              <span className="text-sm text-ink-2">{u.role.name}</span>
              <span className="flex items-center gap-1 justify-self-end">
                {/* The calendar is switched on per person, not given with a role. */}
                <Button
                  size="sm"
                  variant="quiet"
                  disabled={pending || !u.isActive}
                  aria-pressed={u.calendarOn}
                  title={u.calendarOn ? "Their calendar is on: click to switch it off" : "Switch on their calendar (deadlines and reminders)"}
                  onClick={() =>
                    change(
                      u.id,
                      { calendarOn: !u.calendarOn },
                      u.calendarOn ? `${u.fullName}'s calendar switched off` : `${u.fullName}'s calendar switched on`,
                    )
                  }
                >
                  {u.calendarOn ? "Calendar on" : "Calendar off"}
                </Button>
                {u.hasSignature && (
                  <ConfirmButton
                    label="Remove signature"
                    triggerVariant="quiet"
                    triggerSize="sm"
                    title={`Remove ${u.fullName}'s e-signature?`}
                    body="Documents they already signed keep it. Only they can set a new one, on their account page."
                    confirmLabel="Remove"
                    onConfirm={async () => {
                      const r = await removeUserSignature(u.id);
                      if (!r.ok) {
                        toast.error(r.error);
                        return false;
                      }
                      toast.success(`${u.fullName}'s signature removed`);
                      router.refresh();
                    }}
                  />
                )}
              </span>
            </li>
          ))}
        </ul>
      </Sheet>
    </div>
  );
}


// --- Roles & Permissions ---------------------------------------------------

type RoleInput = { name: string; description: string | null; permissions: string[] };

const NEW = "__new__";

export function RolesEditor({ data }: { data: RolesData }) {
  const router = useRouter();
  const [selected, setSelected] = useState<string>(data.roles[0]?.id ?? NEW);
  const [drafts, setDrafts] = useState<Record<string, RoleInput>>({});
  const [errors, setErrors] = useState<{ message: string | null; fields: Record<string, string> }>({
    message: null,
    fields: {},
  });
  const [saving, start] = useTransition();
  const role = data.roles.find((r) => r.id === selected) ?? null;
  const saved: RoleInput = role
    ? { name: role.name, description: role.description, permissions: [...role.permissions].sort() }
    : { name: "", description: null, permissions: [] };
  const draft = drafts[selected] ?? saved;
  const same = (a: RoleInput, b: RoleInput) =>
    a.name.trim() === b.name.trim() &&
    (a.description ?? "").trim() === (b.description ?? "").trim() &&
    a.permissions.join() === [...b.permissions].sort().join();
  const dirty = selected === NEW ? selected in drafts : !same(draft, saved);
  const locked = role?.isSystem ?? false;
  const edit = (change: Partial<RoleInput>) =>
    setDrafts({ ...drafts, [selected]: { ...draft, ...change } });

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
      toast.success(role ? `${input.name} saved` : `${input.name} added`, {
        description: role ? "Applies to users with this role right away." : undefined,
      });
      router.refresh();
    });
  }

  const items = [
    ...data.roles.map((r) => ({
      key: r.id,
      label: r.name,
      detail: `${r.userCount} ${r.userCount === 1 ? "person" : "people"}`,
      unsaved:
        r.id in drafts &&
        !same(drafts[r.id], {
          name: r.name,
          description: r.description,
          permissions: r.permissions,
        }),
    })),
    ...(NEW in drafts || selected === NEW
      ? [{ key: NEW, label: draft.name.trim() || "New role", detail: "Not saved yet", unsaved: true }]
      : []),
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
      <PickList
        title="Roles"
        icon="roles"
        items={items}
        selected={selected}
        onSelect={pick}
        footer={
          <div className="mt-3 px-2">
            <Button
              size="sm"
              variant="quiet"
              icon={<Plus className="size-4" aria-hidden />}
              onClick={() => pick(NEW)}
              disabled={selected === NEW}
            >
              New role
            </Button>
          </div>
        }
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
                <span className="text-meta text-ink-3">
                  In use by {role.userCount} {role.userCount === 1 ? "person" : "people"}
                </span>
              ) : null
            }
          >
            {role ? role.name : "New role"}
          </SectionTitle>
          {locked ? (
            <p className="mt-2 text-meta text-ink-2">
              The Administrator role always has every permission, including ones added later. It
              can&apos;t be changed or deleted, so there&apos;s always a way to fix access. To give
              someone less, make a new role.
            </p>
          ) : (
            <FormGrid className="mt-4">
              <Field label="Name" size="md" error={errors.fields.name}>
                {(p) => (
                  <Input
                    {...p}
                    value={draft.name}
                    onChange={(e) => edit({ name: e.target.value })}
                    autoFocus={selected === NEW}
                  />
                )}
              </Field>
              <Field label="Description" size="full" optional error={errors.fields.description}>
                {(p) => (
                  <Textarea
                    {...p}
                    rows={1}
                    value={draft.description ?? ""}
                    onChange={(e) => edit({ description: e.target.value })}
                  />
                )}
              </Field>
            </FormGrid>
          )}
        </Sheet>
        <Permissions
          catalogue={data.catalogue}
          granted={draft.permissions}
          locked={locked}
          onChange={(permissions) => edit({ permissions })}
        />
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

function Permissions({
  catalogue,
  granted,
  locked,
  onChange,
}: {
  catalogue: PermissionArea[];
  granted: string[];
  locked: boolean;
  onChange: (p: string[]) => void;
}) {
  const has = new Set(granted);
  const groups = [...new Set(catalogue.map((a) => a.group))];

  function toggle(area: PermissionArea, permission: string, on: boolean) {
    const next = new Set(has);
    const view = `${area.key}.view`;
    const hasView = area.actions.some((a) => a.permission === view);
    if (on) {
      next.add(permission);
      if (hasView) next.add(view);
    } else {
      next.delete(permission);
      if (permission === view) {
        for (const a of area.actions) next.delete(a.permission);
      }
    }
    onChange([...next].sort());
  }

  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle icon="password">Permissions</SectionTitle>
      {groups.map((group) => (
        <div key={group} className="mt-4">
          <h3 className="text-caps text-ink-3 uppercase font-semibold text-xs tracking-wider">{group}</h3>
          <ul className="mt-1 divide-y divide-rule">
            {catalogue
              .filter((a) => a.group === group)
              .map((area) => (
                <li key={area.key} className="grid gap-2 py-2.5 md:grid-cols-[16rem_minmax(0,1fr)] md:items-center">
                  <span className="text-sm font-medium text-ink">{area.name}</span>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {area.actions.map((a) => {
                      const on = has.has(a.permission);
                      return (
                        <label
                          key={a.permission}
                          className={`relative inline-flex items-center rounded-full border px-3 py-1 text-meta has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-hema ${
                            on
                              ? "border-hema bg-hema-tint font-semibold text-hema"
                              : "border-rule-strong bg-sheet text-ink-2"
                          } ${locked ? "cursor-default opacity-80" : "cursor-pointer hover:border-hema"}`}
                        >
                          <input suppressHydrationWarning
                            type="checkbox"
                            className="sr-only"
                            checked={on}
                            disabled={locked}
                            onChange={(e) => toggle(area, a.permission, e.target.checked)}
                          />
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
