"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { PermissionGrid } from "@/src/platform/ui/permission-grid";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Choice, Field, FormError, FormGrid, Input, Textarea } from "@/src/platform/ui/field";
import { PickList, SaveBar } from "@/src/platform/ui/pick-list";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { createRole, deleteRole, updateRole, type RoleInput } from "@/src/modules/crm/actions/admin";
import type { PermissionArea, RoleRow, RolesData, Scope } from "@/src/platform/lib/types";
import { SCOPE_TAGS } from "@/src/modules/crm/components/admin/words";

const NEW = "__new";
const EMPTY: RoleInput = { name: "", description: null, scope: "own", permissions: [] };

const asInput = (r: RoleRow): RoleInput => ({ name: r.name, description: r.description, scope: r.scope, permissions: [...r.permissions].sort() });
const same = (a: RoleInput, b: RoleInput) =>
  a.name.trim() === b.name.trim() &&
  (a.description ?? "").trim() === (b.description ?? "").trim() &&
  a.scope === b.scope &&
  a.permissions.join() === [...b.permissions].sort().join();

export function RolesEditor({ data }: { data: RolesData }) {
  const router = useRouter();
  const [selected, setSelected] = useState(data.roles[0]?.id ?? NEW);
  const [drafts, setDrafts] = useState<Record<string, RoleInput>>({});
  const [errors, setErrors] = useState<{ message: string | null; fields: Record<string, string> }>({ message: null, fields: {} });
  const [saving, start] = useTransition();

  const role = data.roles.find((r) => r.id === selected) ?? null;
  const saved = role ? asInput(role) : EMPTY;
  const draft = drafts[selected] ?? saved;
  const dirty = selected === NEW ? selected in drafts : !same(draft, saved);
  const locked = role?.isSystem ?? false;

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
      const input = { ...draft, name: draft.name.trim(), description: draft.description?.trim() || null };
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
        description: role ? "People with this role get the change on their next click." : undefined,
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

  const items = [
    ...data.roles.map((r) => ({
      key: r.id,
      label: r.name,
      detail: `${SCOPE_TAGS[r.scope]} · ${r.userCount} ${r.userCount === 1 ? "person" : "people"}`,
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
              role && !locked && role.userCount > 0 ? (
                <span className="text-meta text-ink-3">
                  In use by {role.userCount} {role.userCount === 1 ? "person" : "people"}
                </span>
              ) : role && !locked ? (
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
          {locked ? (
            <p className="mt-2 text-meta text-ink-2">
              The Administrator role always has every permission, including ones added later, and reaches every record. It can't be
              changed or deleted, so there's always a way to fix access. To give someone less, make a new role.
            </p>
          ) : (
            <FormGrid className="mt-4">
              <Field label="Name" size="md" error={errors.fields.name}>
                {(p) => <Input {...p} value={draft.name} onChange={(e) => edit({ name: e.target.value })} autoFocus={selected === NEW} />}
              </Field>
              <Field label="Description" size="full" optional error={errors.fields.description}>
                {(p) => <Textarea {...p} rows={1} value={draft.description ?? ""} onChange={(e) => edit({ description: e.target.value })} />}
              </Field>
              <div className="sm:col-span-6">
                <Choice<Scope>
                  name="scope"
                  legend="Record access"
                  value={draft.scope}
                  onChange={(scope) => edit({ scope })}
                  options={data.scopes.map((s) => ({ value: s.key, label: s.label }))}
                />
              </div>
            </FormGrid>
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

/** The permission grid, in its sheet (the grid itself is the kit's: PermissionGrid). */
function Permissions({
  catalogue,
  granted,
  locked,
  onChange,
}: {
  catalogue: PermissionArea[];
  granted: string[];
  locked: boolean;
  onChange: (permissions: string[]) => void;
}) {
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle icon="password">Permissions</SectionTitle>
      <p className="mt-1 text-meta text-ink-3">Areas whose screens aren't built yet can be set now; they apply as each one arrives.</p>
      <PermissionGrid catalogue={catalogue} granted={granted} locked={locked} onChange={onChange} />
    </Sheet>
  );
}
