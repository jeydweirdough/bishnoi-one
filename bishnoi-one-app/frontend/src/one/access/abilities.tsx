"use client";

import { Modal } from "antd";
import { Copy } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, Input } from "@/src/platform/ui/field";
import { SaveBar } from "@/src/platform/ui/pick-list";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { roleFromJob, setRoleAbilities } from "./actions";
import { moduleLabel } from "./labels";
import type { AbilityCatalogue, AccessModule, AccessRole } from "./types";

// Roles in plain words (feature plan step 6, decisions 20–25): Bishnoi One defines the abilities and
// the ready-made job roles; a company copies a job role and switches abilities on or off. Each
// ability brings the permissions it needs in every app, so nobody picks "View" or "Create" by hand.

type Held = Record<string, number | null>;
const held = (role: AccessRole): Held => Object.fromEntries(role.abilities.map((a) => [a.key, a.limit]));

/** A role's abilities, by group, each switched on or off where it's shown, a limit beside those that take one. */
export function AbilitiesSection({ role, catalogue, modules }: { role: AccessRole; catalogue: AbilityCatalogue; modules: AccessModule[] }) {
  const router = useRouter();
  const [saving, start] = useTransition();
  const [draft, setDraft] = useState<Held>(held(role));
  const [scopes, setScopes] = useState<Record<string, string>>({ ...role.scopes });
  const [error, setError] = useState<string | null>(null);
  const have = new Set(modules.map((m) => m.key));
  const scoped = modules.filter((m) => m.scopes.length > 0);
  const dirty = JSON.stringify(Object.entries(draft).sort()) !== JSON.stringify(Object.entries(held(role)).sort()) || scoped.some((m) => (scopes[m.key] ?? "") !== (role.scopes[m.key] ?? ""));
  const legacy = role.abilities.length === 0 && Object.values(role.permissions).some((p) => p.length > 0);

  function toggle(key: string, on: boolean) {
    const next = { ...draft };
    if (on) next[key] = null;
    else delete next[key];
    setDraft(next);
  }

  function save() {
    start(async () => {
      const r = await setRoleAbilities(role.id, Object.entries(draft).map(([key, limit]) => ({ key, limit })), scopes);
      if (!r.ok) return setError(r.error);
      setError(null);
      toast.success(`${role.name} saved`, { description: "Every app is told now; people with this role get it on their next click." });
      router.refresh();
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-4">
      <SectionTitle icon="roles">What this role can do</SectionTitle>
      {legacy && (
        <p className="mt-1 text-meta text-promo-ink">
          This role was made with technical permissions. Switching abilities on here replaces them with what the abilities need.
        </p>
      )}
      {scoped.length > 0 && (
        <div className="mt-3 space-y-2">
          {scoped.map((m) => (
            <Choice<string>
              key={m.key}
              name={`sees-${m.key}`}
              legend={`Whose records it sees in ${moduleLabel(m)}`}
              value={scopes[m.key] ?? m.scopes[0].key}
              onChange={(v) => setScopes({ ...scopes, [m.key]: v })}
              options={m.scopes.map((s) => ({ value: s.key, label: s.label }))}
            />
          ))}
        </div>
      )}
      <div className="mt-4 grid gap-5 md:grid-cols-2">
        {catalogue.groups.map((g) => (
          <fieldset key={g.name}>
            <legend className="mb-1.5 text-caps text-ink-3 uppercase">{g.name}</legend>
            <ul className="space-y-1">
              {g.abilities.map((a) => {
                const on = a.key in draft;
                const usable = a.apps.some((k) => have.has(k));
                return (
                  <li key={a.key} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <label className={`inline-flex min-h-9 flex-1 cursor-pointer items-center gap-2 text-sm ${usable ? "text-ink" : "text-ink-3"}`}>
                      <input suppressHydrationWarning type="checkbox" checked={on} onChange={(e) => toggle(a.key, e.target.checked)} />
                      {a.label}
                      {!usable && <span className="text-meta">(an app your company hasn&apos;t got)</span>}
                    </label>
                    {on && a.limit && (
                      <span className="inline-flex items-center gap-1.5 text-meta text-ink-3">
                        {a.limit}
                        <Input
                          aria-label={`${a.label}: ${a.limit}`}
                          type="number"
                          min={0}
                          className="w-28"
                          value={draft[a.key] ?? ""}
                          onChange={(e) => setDraft({ ...draft, [a.key]: e.target.value === "" ? null : Math.max(0, Number(e.target.value)) })}
                          placeholder="No limit"
                        />
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </fieldset>
        ))}
      </div>
      {dirty && (
        <div className="mt-4">
          <SaveBar
            what={<>Unsaved changes to <strong>{role.name}</strong></>}
            saving={saving}
            onSave={save}
            onDiscard={() => (setDraft(held(role)), setScopes({ ...role.scopes }), setError(null))}
            error={error ? <p className="text-meta text-danger">{error}</p> : undefined}
          />
        </div>
      )}
    </Sheet>
  );
}

/** Copy one of Bishnoi One's job roles: the start of most roles (decision 23). */
export function CopyJobRole({ catalogue, onMade }: { catalogue: AbilityCatalogue; onMade: (id: string) => void }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, start] = useTransition();
  const labels = Object.fromEntries(catalogue.groups.flatMap((g) => g.abilities.map((a) => [a.key, a.label])));
  const job = catalogue.jobRoles.find((j) => j.key === picked);

  function make() {
    if (!job) return;
    start(async () => {
      const r = await roleFromJob(job.key, name.trim() || null);
      if (!r.ok) return setError(r.error);
      toast.success(`${r.data.name} added`, { description: "Adjust its abilities, then give it to people on People." });
      setOpen(false);
      setPicked(null);
      setName("");
      setError(null);
      router.refresh();
      onMade(r.data.id);
    });
  }

  return (
    <>
      <Button size="sm" variant="quiet" icon={<Copy className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Copy a job role
      </Button>
      <Modal open={open} title="Copy a job role" onCancel={() => !busy && setOpen(false)} onOk={make} okText="Copy" okButtonProps={{ disabled: !job }} confirmLoading={busy} width={640} destroyOnHidden>
        <p className="text-sm text-ink-2">Ready-made by Bishnoi One. Your copy is yours to rename and adjust.</p>
        <ul className="mt-3 max-h-80 divide-y divide-rule overflow-y-auto rounded-lg border border-rule">
          {catalogue.jobRoles.map((j) => (
            <li key={j.key}>
              <label className={`flex cursor-pointer gap-3 px-3 py-2.5 ${picked === j.key ? "bg-mint" : "hover:bg-bench"}`}>
                <input suppressHydrationWarning type="radio" name="job" checked={picked === j.key} onChange={() => (setPicked(j.key), setName(j.name))} className="mt-1" />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-ink">
                    {j.name} <span className="font-normal text-ink-3">· sees {j.sees.toLowerCase()}</span>
                  </span>
                  <span className="block text-meta text-ink-3">{j.admin ? "Everything, in every app" : j.abilities.map((a) => labels[a] ?? a).join(" · ")}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        {job && (
          <div className="mt-3">
            <Field label="Name of your copy" size="full" error={error ?? undefined}>
              {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />}
            </Field>
          </div>
        )}
      </Modal>
    </>
  );
}
