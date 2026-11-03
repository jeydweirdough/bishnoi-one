"use client";

import { Switch } from "antd";
import { ChevronRight, Plus, ShieldCheck, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";
import { AboutTip } from "@/src/platform/ui/about-tip";
import { InlineMessage } from "@/src/platform/ui/alert";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Choice, Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { PermissionMatrix } from "@/src/platform/ui/permission-matrix";
import { PickList, SaveBar } from "@/src/platform/ui/pick-list";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { createRole, deleteRole, importRoles, standardDefaults, updateRole } from "./actions";
import { moduleLabel, ROLE_ACTIONS } from "./labels";
import { AbilitiesSection, CopyJobRole } from "./abilities";
import type { AbilityCatalogue, AccessData, AccessModule, AccessRole, RoleInput } from "./types";

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
export function AccessRolesEditor({ data, catalogue }: { data: AccessData; catalogue: AbilityCatalogue | null }) {
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
        description: "Every module is told now; employees with this role get it on their next click.",
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

  const [actions, setActions] = useState<HTMLElement | null>(null);
  useEffect(() => setActions(document.getElementById(ROLE_ACTIONS)), []);
  const employees = (n: number) => `${n} ${n === 1 ? "employee" : "employees"}`;

  if (data.roles.length === 0 && selected !== NEW) {
    return (
      <Sheet>
        <Empty
          icon="roles"
          title="No roles yet"
          actions={
            <>
              <AsyncButton onRun={bringIn}>Bring in today&apos;s roles</AsyncButton>
              {catalogue && <CopyJobRole catalogue={catalogue} onMade={pick} />}
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
      detail: summary(r, data.modules),
      aside: (
        <span title={employees(r.people)} className={`inline-flex shrink-0 items-center gap-1 text-meta ${r.people ? "text-ink-2" : "text-ink-3"}`}>
          <Users className="size-3.5" aria-hidden />
          <span className="sr-only">Employees: </span>
          {r.people}
        </span>
      ),
      unsaved: r.id in drafts && !same(drafts[r.id], asInput(r)),
    })),
    ...(NEW in drafts || selected === NEW ? [{ key: NEW, label: draft.name.trim() || "New role", detail: "Not saved yet", unsaved: true }] : []),
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
      {/* At the top right, as Add employee is, not under a long list. */}
      {actions &&
        createPortal(
          <>
            {catalogue && <CopyJobRole catalogue={catalogue} onMade={pick} />}
            <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => pick(NEW)} disabled={selected === NEW}>
              New role
            </Button>
          </>,
          actions,
        )}

      <PickList bare title="Roles" items={items} selected={selected} onSelect={pick} />

      <div className="min-w-0 space-y-5">
        <Sheet className="space-y-4 px-5 pt-4 pb-5">
          <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
            <div className="w-full max-w-md">
              <Field label="Name" error={errors.fields.name}>
                {(p) => <Input {...p} value={draft.name} onChange={(e) => edit({ name: e.target.value })} autoFocus={selected === NEW} />}
              </Field>
            </div>
            {role && (
              <div className="ml-auto flex items-center gap-1 pt-7">
                {role.people > 0 ? (
                  <Link href="/platform/roles/people" className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm text-ink-2 hover:bg-bench hover:text-ink">
                    <Users className="size-4 shrink-0" aria-hidden />
                    {employees(role.people)}
                  </Link>
                ) : (
                  <ConfirmButton
                    label="Delete"
                    icon={<Trash2 className="size-4" aria-hidden />}
                    title={`Delete ${role.name}?`}
                    body="Nobody has this role, so nothing else changes."
                    confirmLabel="Delete role"
                    triggerSize="sm"
                    triggerVariant="quiet"
                    onConfirm={remove}
                  />
                )}
              </div>
            )}
          </div>
          <Field label="Description" optional error={errors.fields.description}>
            {(p) => <Textarea {...p} rows={1} value={draft.description ?? ""} onChange={(e) => edit({ description: e.target.value })} />}
          </Field>
          {/* Two choices, so a switch: on, the role is each app's Administrator. */}
          <div className="flex min-h-9 flex-wrap items-center gap-x-3 gap-y-1">
            <Switch id="role-full-access" checked={draft.isAdmin} onChange={(on) => edit({ isAdmin: on })} />
            <label htmlFor="role-full-access" className="cursor-pointer text-sm font-medium text-ink">
              Full access
            </label>
            <AboutTip>Every permission in every app, including ones added later, and every record. Someone must always have it, so there&apos;s always a way to fix access.</AboutTip>
            {draft.isAdmin && (
              <span className="inline-flex items-center gap-1.5 text-meta text-sage-deep">
                <ShieldCheck className="size-3.5" aria-hidden />
                Administrator in every app
              </span>
            )}
          </div>
        </Sheet>

        {!draft.isAdmin && (
          <>
            <StartFrom
              onLoad={(permissions, scopes) => {
                edit({ permissions, scopes });
                toast.info("Loaded into this role: change what you like, then Save.");
              }}
            />
            <div className="space-y-5">
              {data.modules.map((m) => (
                <ModuleSection
                  key={`${selected}-${m.key}`}
                  module={m}
                  granted={draft.permissions[m.key] ?? []}
                  scope={draft.scopes[m.key] ?? m.scopes[0]?.key ?? ""}
                  error={errors.fields.permissions}
                  onPermissions={(perms) => edit({ permissions: { ...draft.permissions, [m.key]: perms } })}
                  onScope={(scope) => edit({ scopes: { ...draft.scopes, [m.key]: scope } })}
                />
              ))}
            </div>
            {/* The plain-word abilities, the older way (step 6): saving them sets the permissions above from them. */}
            {role && catalogue && (
              <details className="group">
                <summary className="cursor-pointer px-1 text-meta text-ink-3">Plain-word abilities (the older way)</summary>
                <div className="mt-3">
                  <AbilitiesSection key={`${role.id}-${JSON.stringify(role.abilities)}-${JSON.stringify(role.scopes)}`} role={role} catalogue={catalogue} modules={data.modules} />
                </div>
              </details>
            )}
          </>
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

/** Start a role from what Mentor, Coach or Coachee may do by default: loaded into the role being edited, saved only when you Save. */
function StartFrom({ onLoad }: { onLoad: (permissions: Record<string, string[]>, scopes: Record<string, string>) => void }) {
  const [busy, start] = useTransition();
  const pick = (level: "mentor" | "coach" | "coachee") =>
    start(async () => {
      const r = await standardDefaults(level);
      if (!r.ok) return void toast.error(r.error);
      onLoad(r.data.permissions, r.data.scopes);
    });
  return (
    <Sheet className="flex flex-wrap items-center gap-x-3 gap-y-2 px-5 py-3">
      <span className="text-sm font-medium text-ink">Start from</span>
      <AboutTip>
        What each level may do by default, in every app: a Coachee creates, reads, updates, submits and prints their own; a Coach also approves, rejects, returns, assigns and exports for their coachees; a Mentor also imports, cancels,
        reopens and transfers for everyone under them. Delete, Post and Void are never given by default. It replaces this role&apos;s permissions below until you Save.
      </AboutTip>
      {(["coachee", "coach", "mentor"] as const).map((level) => (
        <Button key={level} size="sm" disabled={busy} onClick={() => pick(level)}>
          {level.charAt(0).toUpperCase() + level.slice(1)}
        </Button>
      ))}
    </Sheet>
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
      <button suppressHydrationWarning type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-2 py-1 text-left">
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
            <PermissionMatrix catalogue={m.areas} granted={granted} onChange={onPermissions} />
          </>
        ))}
    </Sheet>
  );
}
