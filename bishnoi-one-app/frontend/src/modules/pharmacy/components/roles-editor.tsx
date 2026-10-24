"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/pharmacy/platform/ui/button";
import { ConfirmButton } from "@/src/modules/pharmacy/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/modules/pharmacy/platform/ui/field";
import { createRole, deleteRole, updateRole } from "@/src/modules/pharmacy/actions/pharmacy";
import type { PermissionArea, RoleRow } from "@/src/modules/pharmacy/lib/types";

/**
 * What each role may do: one grid of every area and its actions per role.
 * Administrator always holds everything and can't be changed. Verifying a
 * prescription and dispensing it are separate ticks on purpose.
 */
export function RolesEditor({ roles, catalogue }: { roles: RoleRow[]; catalogue: PermissionArea[] }) {
  const [adding, setAdding] = useState(false);
  return (
    <div className="space-y-4">
      {roles.map((role) => (
        <RoleCard key={`${role.id}-${role.permissions.join()}-${role.name}`} role={role} catalogue={catalogue} />
      ))}
      {adding ? (
        <RoleCard catalogue={catalogue} onDone={() => setAdding(false)} />
      ) : (
        <Button onClick={() => setAdding(true)} icon={<Plus className="size-4" aria-hidden />}>
          Add a role
        </Button>
      )}
    </div>
  );
}

function RoleCard({ role, catalogue, onDone }: { role?: RoleRow; catalogue: PermissionArea[]; onDone?: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [naming, setNaming] = useState(!role);
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [granted, setGranted] = useState<Set<string>>(new Set(role?.permissions ?? ["dashboard.view"]));
  const [error, setError] = useState<string | null>(null);
  const locked = role?.isSystem ?? false;
  const dirty = !role || naming || [...granted].sort().join() !== [...role.permissions].sort().join();
  const groups = [...new Set(catalogue.map((a) => a.group))];

  function toggle(permission: string) {
    const next = new Set(granted);
    if (next.has(permission)) next.delete(permission);
    else next.add(permission);
    setGranted(next);
  }

  function save() {
    start(async () => {
      const input = { name: name.trim(), description: description.trim() || null, permissions: [...granted] };
      const result = role ? await updateRole(role.id, input) : await createRole(input);
      if (result.ok) {
        toast.success(role ? "Role saved" : "Role added", { description: result.data.name });
        setNaming(false);
        setError(null);
        onDone?.();
        router.refresh();
        return;
      }
      setError(result.fields?.name ?? result.error);
    });
  }

  return (
    <section className="rounded-[3px] bg-sheet shadow-sheet">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-rule px-5 py-4">
        {naming ? (
          <div className="grid w-full gap-3 sm:grid-cols-2">
            <Field label="Role name">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} autoFocus />}</Field>
            <Field label="What it's for" optional>
              {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} />}
            </Field>
          </div>
        ) : (
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h2 className="text-heading text-ink">{role?.name}</h2>
              {!locked && (
                <button type="button" onClick={() => setNaming(true)} title={`Rename ${role?.name}`} aria-label={`Rename ${role?.name}`} className="rounded-[3px] p-1 text-ink-3 hover:bg-hema-tint hover:text-hema">
                  <Pencil className="size-3.5" aria-hidden />
                </button>
              )}
              {role && !locked && role.userCount === 0 && (
                <ConfirmButton
                  label=""
                  icon={<Trash2 className="size-3.5" aria-hidden />}
                  triggerVariant="quiet"
                  triggerSize="sm"
                  triggerClassName="!h-7 !px-1.5 text-ink-3"
                  triggerTitle={`Delete ${role.name}`}
                  title={`Delete the ${role.name} role?`}
                  confirmLabel="Delete role"
                  onConfirm={async () => {
                    const r = await deleteRole(role.id);
                    if (!r.ok) toast.error(r.error);
                    return r.ok;
                  }}
                />
              )}
            </div>
            <p className="text-meta text-ink-3">
              {role?.description ?? ""} {role ? `· ${role.userCount} ${role.userCount === 1 ? "person" : "people"}` : ""}
            </p>
          </div>
        )}
      </header>
      <div className="grid gap-x-8 gap-y-4 px-5 py-4 md:grid-cols-2">
        {groups.map((group) => (
          <fieldset key={group} className="min-w-0">
            <legend className="mb-1.5 text-caps text-ink-3 uppercase">{group}</legend>
            <ul className="space-y-2">
              {catalogue
                .filter((a) => a.group === group)
                .map((area) => (
                  <li key={area.key}>
                    <p className="text-sm font-medium text-ink">{area.name}</p>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                      {area.actions.map((a) => (
                        <label key={a.permission} className={`inline-flex items-center gap-1.5 text-meta ${locked ? "text-ink-3" : "cursor-pointer text-ink-2"}`}>
                          <input
                            type="checkbox"
                            className="size-3.5 accent-[var(--color-hema)]"
                            checked={locked || granted.has(a.permission)}
                            disabled={locked}
                            onChange={() => toggle(a.permission)}
                          />
                          {a.label}
                        </label>
                      ))}
                    </div>
                  </li>
                ))}
            </ul>
          </fieldset>
        ))}
      </div>
      {!locked && (
        <footer className="flex flex-wrap items-center gap-2 border-t border-rule px-5 py-3">
          <Button variant="primary" size="sm" loading={pending} disabled={!dirty || !name.trim()} onClick={save}>
            {role ? "Save role" : "Add role"}
          </Button>
          {(!role || naming) && (
            <Button
              size="sm"
              variant="quiet"
              onClick={() => {
                setNaming(false);
                setName(role?.name ?? "");
                onDone?.();
              }}
            >
              Cancel
            </Button>
          )}
          <FormError message={error} />
        </footer>
      )}
      {locked && <p className="border-t border-rule px-5 py-3 text-meta text-ink-3">Always holds everything, including permissions added later. Make a new role to hand out less.</p>}
    </section>
  );
}
