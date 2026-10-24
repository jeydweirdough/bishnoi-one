"use client";

import { ChevronRight, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { InlineMessage } from "@/src/platform/ui/alert";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Choice, Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { PermissionGrid } from "@/src/platform/ui/permission-grid";
import { PickList, SaveBar } from "@/src/platform/ui/pick-list";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { createRole, deleteRole, importRoles, updateRole } from "./actions";
import { moduleLabel } from "./labels";
import type { AccessData, AccessModule, AccessRole, RoleInput } from "./types";

const NEW = "__new";
const EMPTY: RoleInput = { name: "", description: null, isAdmin: false, permissions: {}, scopes: {} };

const sorted = (r: Record<string, string[]>): Record<string, string[]> =>
  Object.fromEntries(
    Object.keys(r)
      .filter((k) => r[k].length > 0)
      .sort()
      .map((k) => [k, [...r[k]].sort()]),
  );
const asInput = (r: AccessRole): RoleInput => ({ name: r.name, description: r.description, isAdmin: r.isAdmin, permissions: sorted(r.permissions), scopes: { ...r.scopes } });
const same = (a: RoleInput, b: RoleInput) =>
  a.name.trim() === b.name.trim() &&
  (a.description ?? "").trim() === (b.description ?? "").trim() &&
  a.isAdmin === b.isAdmin &&
  JSON.stringify(sorted(a.permissions)) === JSON.stringify(sorted(b.permissions)) &&
  JSON.stringify(Object.entries(a.scopes).sort()) === JSON.stringify(Object.entries(b.scopes).sort());

/** What a role reaches, in a few words, for the list. */
function summary(role: AccessRole, modules: AccessModule[]): string {
  if (role.isAdmin) return "Everything";
  const inMods = modules.filter((m) => (role.permissions[m.key] ?? []).length > 0).map(moduleLabel);
  return inMods.length ? inMods.join(", ") : "Nothing yet";
}

/**
 * A company's roles, for every module at once (decided 2026-10-23): pick one on
 * the left; on the right its name, then each module's permissions and, where the
 * module has them, whose records it reaches.
 */
export function AccessRolesEditor({ data }: { data: AccessData }) {
  const router = useRouter();
  const [selected, setSelected] = useState(data.roles[0]?.id ?? NEW);
  const [drafts, setDrafts] = useState<Record<string, RoleInput>>({});
  const [errors, setErrors] = useState<{ message: string | null; fields: Record<string, string> }>({ message: null, fields: {} });
  const [saving, start] = useTransition();

  const role = data.roles.find((r) => r.id === selected) ?? null;
  const saved = role ? asInput(role) : EMPTY;
  const draft = drafts[selected] ?? saved;
  const dirty = selected === NEW ? selected in drafts : !same(draft, saved);

  function edit(change: Partial<RoleInput>) {
    setDrafts({ ...drafts, [selected]: { ...draft, ...change } });
  }

  function pick(id: string) {
    setSelected(id);
    setErrors({ message: null, fields: {} });
  }

  function discard() {
    const next = { ...drafts };
    delete next[selected];
    setDrafts(next);
    setErrors({ message: null, fields: {} });
    if (selected === NEW) setSelected(data.roles[0]?.id ?? NEW);
  }

  function save() {
    start(async () => {
      // Only the modules that can be reached are sent: one out of reach keeps what it had.
      const reachable = new Set(data.modules.filter((m) => m.reachable).map((m) => m.key));
      const only = <T,>(r: Record<string, T>) => Object.fromEntries(Object.entries(r).filter(([k]) => reachable.has(k)));
      const input: RoleInput = {
        ...draft,
        name: draft.name.trim(),
        description: draft.description?.trim() || null,
        permissions: draft.isAdmin ? {} : only(Object.fromEntries(data.modules.map((m) => [m.key, draft.permissions[m.key] ?? []]))),
        scopes: draft.isAdmin ? {} : only(draft.scopes),
      };
      const result = role ? await updateRole(role.id, input) : await createRole(input);
      if (!result.ok) {
        setErrors({ message: result.error, fields: result.fields ?? {} });
        return;
      }
      const next = { ...drafts };
      delete next[selected];
      setDrafts(next);
      setErrors({ message: null, fields: {} });
      setSelected(result.data.id);
      toast.success(role ? `${result.data.name} saved` : `${result.data.name} added`, {
        description: "Every module is told now; people with this role get it on their next click.",
      });
      router.refresh();
    });
  }

  async function remove(): Promise<boolean> {
    if (!role) return false;
    const result = await deleteRole(role.id);
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    toast.success(`${role.name} deleted`);
    setSelected(data.roles.find((r) => r.id !== role.id)?.id ?? NEW);
    router.refresh();
    return true;
  }

  async function bringIn() {
    const r = await importRoles();
    if (!r.ok) toast.error(r.error);
    else {
      toast.success(`${r.data.rolesMade} ${r.data.rolesMade === 1 ? "role" : "roles"} brought in`);
      router.refresh();
    }
  }

  if (data.roles.length === 0 && selected !== NEW) {
    return (
      <Sheet>
        <Empty
          icon="roles"
          title="No roles yet"
          actions={
            <>
              <AsyncButton onRun={bringIn}>Bring in today&apos;s roles</AsyncButton>
              <Button onClick={() => pick(NEW)}>New role</Button>
            </>
          }
        >
          Bring in the roles each module has today (the same names become one role), or start one of your own.
        </Empty>
      </Sheet>
    );
  }

  const items = [
    ...data.roles.map((r) => ({
      key: r.id,
      label: r.name,
      detail: `${summary(r, data.modules)} · ${r.people} ${r.people === 1 ? "person" : "people"}`,
      unsaved: r.id in drafts && !same(drafts[r.id], asInput(r)),
    })),
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
        footer={
          <div className="mt-3 px-2">
            <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => pick(NEW)} disabled={selected === NEW}>
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
              role && role.people > 0 ? (
                <span className="text-meta text-ink-3">
                  In use by {role.people} {role.people === 1 ? "person" : "people"}
                </span>
              ) : role ? (
                <ConfirmButton
                  label="Delete"
                  title={`Delete ${role.name}?`}
                  body="Nobody has this role, so nothing else changes."
                  confirmLabel="Delete role"
                  triggerSize="sm"
                  triggerVariant="quiet"
                  onConfirm={remove}
                />
              ) : null
            }
          >
            {role ? role.name : "New role"}
          </SectionTitle>
          <div className="mt-4 grid gap-5 sm:grid-cols-2">
            <Field label="Name" error={errors.fields.name}>
              {(p) => <Input {...p} value={draft.name} onChange={(e) => edit({ name: e.target.value })} autoFocus={selected === NEW} />}
            </Field>
            <Field label="Description" optional error={errors.fields.description}>
              {(p) => <Textarea {...p} rows={1} value={draft.description ?? ""} onChange={(e) => edit({ description: e.target.value })} />}
            </Field>
            <div className="sm:col-span-2">
              <Choice<"chosen" | "all">
                name="reach"
                legend="What it allows"
                value={draft.isAdmin ? "all" : "chosen"}
                onChange={(v) => edit({ isAdmin: v === "all" })}
                options={[
                  { value: "chosen", label: "What's chosen below, module by module" },
                  { value: "all", label: "Everything, in every module (Administrator)" },
                ]}
              />
            </div>
          </div>
        </Sheet>

        {draft.isAdmin ? (
          <Sheet className="px-5 py-4">
            <p className="text-meta text-ink-2">
              This role is each module&apos;s Administrator: every permission there, including ones added later, and every record. Someone must always
              have it, so there&apos;s always a way to fix access.
            </p>
          </Sheet>
        ) : (
          data.modules.map((m) => (
            <ModuleSection
              key={`${selected}-${m.key}`}
              module={m}
              granted={draft.permissions[m.key] ?? []}
              scope={draft.scopes[m.key] ?? m.scopes[0]?.key ?? ""}
              error={errors.fields.permissions}
              onPermissions={(perms) => edit({ permissions: { ...draft.permissions, [m.key]: perms } })}
              onScope={(scope) => edit({ scopes: { ...draft.scopes, [m.key]: scope } })}
            />
          ))
        )}

        {dirty && (
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

function ModuleSection({
  module: m,
  granted,
  scope,
  error,
  onPermissions,
  onScope,
}: {
  module: AccessModule;
  granted: string[];
  scope: string;
  error?: string;
  onPermissions: (permissions: string[]) => void;
  onScope: (scope: string) => void;
}) {
  const name = moduleLabel(m);
  const scopeLabel = m.scopes.find((s) => s.key === scope)?.label;
  // Folded under its name, open where the role already holds something: only what's being worked on is on screen.
  const [open, setOpen] = useState(granted.length > 0);
  return (
    <Sheet className="px-5 pt-3 pb-3">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-2 py-1 text-left">
        <ChevronRight className={`size-4 text-ink-3 transition-transform ${open ? "rotate-90" : ""}`} aria-hidden />
        <span className="text-base font-semibold text-ink">{name}</span>
        <span className="ml-auto text-meta text-ink-3">
          {granted.length ? `${granted.length} allowed${scopeLabel ? ` · ${scopeLabel.toLowerCase()}` : ""}` : "Nothing allowed"}
        </span>
      </button>
      {open &&
        (!m.reachable ? (
          <div className="mt-2 mb-2">
            <InlineMessage tone="warn">{name} can&apos;t be reached right now, so what this role may do there can&apos;t be changed. It keeps what it has.</InlineMessage>
          </div>
        ) : (
          <>
            {m.scopes.length > 0 && (
              <div className="mt-3">
                <Choice<string> name={`scope-${m.key}`} legend="Record access" value={scope} onChange={onScope} options={m.scopes.map((s) => ({ value: s.key, label: s.label }))} />
              </div>
            )}
            {error && <p className="mt-2 text-meta text-danger">{error}</p>}
            <PermissionGrid catalogue={m.areas} granted={granted} onChange={onPermissions} />
          </>
        ))}
    </Sheet>
  );
}
