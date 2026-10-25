"use client";

import { Plus, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/admin/platform/ui/button";
import { Field, FormError, Input } from "@/src/modules/admin/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/modules/admin/platform/ui/sheet";
import { saveApps } from "@/src/modules/admin/actions/admin";
import type { AppLink } from "@/src/modules/admin/platform/lib/types";
import { PickList, SaveBar } from "@/src/modules/admin/platform/ui/pick-list";

// Settings → Apps: the other applications this company reaches from Bishnoi One.
//
// Bishnoi One is the hub — people, customers, products, prices and roles live here —
// and other applications do their own work beside it. Which ones a company has,
// and where they are, is the company's own setting: adding another one later is
// a name and a link typed here, not a deployment.
//
// What an application can *do* stays in code, because those are permissions
// with meaning (the Orders app's order steps). This screen only says which
// applications this company has and where they live.

type Draft = {
  /** The screen's own handle on a row, so a new one has something to be keyed
   *  by before the API has given it a code. */
  key: string;
  code: string | null;
  name: string;
  url: string;
  description: string;
  icon: string | null;
  isActive: boolean;
};

let counter = 0;
const newKey = () => `new-${++counter}`;

const toDraft = (a: AppLink): Draft => ({
  key: a.code,
  code: a.code,
  name: a.name,
  url: a.url,
  description: a.description,
  icon: a.icon,
  isActive: a.isActive,
});

/** What the API is told, and so what "changed" means. The key is the screen's, not the app's. */
const payload = (rows: Draft[]) =>
  rows.map((d) => ({
    code: d.code,
    name: d.name.trim(),
    url: d.url.trim(),
    description: d.description.trim(),
    icon: d.icon,
    isActive: d.isActive,
  }));

const same = (a: Draft[], b: Draft[]) => JSON.stringify(payload(a)) === JSON.stringify(payload(b));

export function AppsEditor({ apps }: { apps: AppLink[] }) {
  const saved = apps.map(toDraft);
  // Nothing typed yet means "whatever the server says", so a save hands the
  // screen back to it and a new app picks up its real code.
  const [draft, setDraft] = useState<Draft[] | null>(null);
  const [at, setAt] = useState(0);
  const [saving, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [problems, setProblems] = useState<Record<string, string>>({});

  const rows = draft ?? saved;
  const dirty = draft !== null && !same(draft, saved);
  const builtIn = new Set(apps.filter((a) => a.isBuiltIn).map((a) => a.code));
  const here = Math.min(at, rows.length - 1);
  const current = rows[here];

  // Which rows have been touched, so the picker can say so without the person
  // having to open each one.
  const was = new Map(saved.map((d) => [d.code, d]));
  const changed = (d: Draft) => {
    if (draft === null) return false;
    const before = d.code === null ? undefined : was.get(d.code);
    return before === undefined || !same([d], [before]);
  };

  const change = (patch: Partial<Draft>) => setDraft(rows.map((d, i) => (i === here ? { ...d, ...patch } : d)));

  function add() {
    setDraft([...rows, { key: newKey(), code: null, name: "", url: "", description: "", icon: null, isActive: true }]);
    setAt(rows.length);
    setError(null);
  }

  function remove(i: number) {
    setDraft(rows.filter((_, n) => n !== i));
    setAt(Math.max(0, i - 1));
  }

  function save() {
    // Keyed by row and field, so each complaint sits under the box it is about.
    const found: Record<string, string> = {};
    const seen = new Set<string>();
    rows.forEach((d, i) => {
      const name = d.name.trim();
      if (name.length < 2) found[`${i}.name`] = "Give it a name.";
      else if (seen.has(name.toLowerCase())) found[`${i}.name`] = "Two apps cannot share a name.";
      seen.add(name.toLowerCase());
      if (d.url.trim() && !/^https?:\/\/\S+$/.test(d.url.trim()))
        found[`${i}.url`] = "Give the full address, starting with http:// or https://.";
    });
    setProblems(found);
    const first = Object.keys(found)[0];
    if (first !== undefined) {
      setAt(Number(first.split(".")[0]));
      return setError("Some of these need a look.");
    }
    start(async () => {
      const result = await saveApps(payload(rows));
      if (!result.ok) return setError(result.error);
      setError(null);
      setProblems({});
      setDraft(null);
      toast.success("Apps saved", { description: "Your people see the change the next time they sign in." });
    });
  }

  return (
    <>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[19rem_minmax(0,1fr)] lg:items-start">
        <PickList
          title="Your apps"
          icon="apps"
          items={rows.map((d, i) => ({
            key: d.key,
            label: d.name.trim() || "Untitled app",
            detail: !d.isActive ? "Switched off" : d.url.trim() ? d.url.replace(/^https?:\/\//, "") : "No address yet",
            unsaved: changed(d) || Boolean(problems[`${i}.name`] || problems[`${i}.url`]),
          }))}
          selected={current?.key ?? ""}
          onSelect={(key) => {
            setAt(rows.findIndex((d) => d.key === key));
            setError(null);
          }}
          footer={
            <Button size="sm" variant="quiet" className="mt-1 ml-1" icon={<Plus className="size-4" aria-hidden />} onClick={add}>
              Add an app
            </Button>
          }
        />

        <div className="min-w-0">
          {!current ? (
            <Sheet className="px-6 py-10 text-center">
              <h2 className="text-heading">No apps yet</h2>
              <p className="mx-auto mt-1 max-w-md text-sm text-ink-2">
                Add the applications your people use beside Bishnoi One. Each one appears in the sidebar of everyone whose role reaches
                it, and opens already signed in.
              </p>
            </Sheet>
          ) : (
            <Sheet className="max-w-[40rem] px-5 pt-4 pb-5">
              <SectionTitle icon="apps">{current.name.trim() || "New app"}</SectionTitle>
              <p className="mb-5 text-meta text-ink-3">
                {builtIn.has(current.code ?? "")
                  ? "This one comes with Bishnoi One. It can be renamed, pointed somewhere else or switched off, but not removed: its order steps are granted in Roles and permissions whether or not there is a link."
                  : "An app of your own. Bishnoi One sends people to it already signed in; what they may do once they are there is up to the app."}
              </p>

              <div className="space-y-5">
                <Field label="Name" hint="What the sidebar calls it" error={problems[`${here}.name`]}>
                  {(p) => (
                    <Input
                      {...p}
                      value={current.name}
                      maxLength={80}
                      autoComplete="off"
                      className="max-w-xs"
                      placeholder="e.g. Warehouse"
                      onChange={(e) => change({ name: e.target.value })}
                    />
                  )}
                </Field>

                <Field
                  label="Address"
                  optional
                  error={problems[`${here}.url`]}
                  hint="Where it lives. Leave it empty until you know — an app with no address is never offered to anyone."
                >
                  {(p) => (
                    <Input
                      {...p}
                      value={current.url}
                      maxLength={300}
                      inputMode="url"
                      autoComplete="off"
                      spellCheck={false}
                      placeholder="https://orders.yourcompany.com"
                      onChange={(e) => change({ url: e.target.value })}
                    />
                  )}
                </Field>

                <Field label="What it is" optional hint="One line, for whoever wonders">
                  {(p) => (
                    <Input
                      {...p}
                      value={current.description}
                      maxLength={200}
                      placeholder="e.g. Stock counts and put-away"
                      onChange={(e) => change({ description: e.target.value })}
                    />
                  )}
                </Field>

                <label className="flex items-start gap-2 text-sm">
                  <input suppressHydrationWarning
                    type="checkbox"
                    checked={current.isActive}
                    onChange={(e) => change({ isActive: e.target.checked })}
                    className="mt-0.5 size-4 accent-hema"
                  />
                  <span>
                    On
                    <span className="block text-meta text-ink-3">
                      Switched off, it stays here with everything it says, and nobody sees it in their sidebar.
                    </span>
                  </span>
                </label>
              </div>

              {!builtIn.has(current.code ?? "") && (
                <div className="mt-5 border-t border-rule pt-4">
                  <p className="text-meta text-ink-3">
                    An app of your own shows only to people whose role reaches it. Give it out in{" "}
                    <b className="font-semibold text-ink-2">Roles &amp; permissions</b>, the same as a department.
                  </p>
                  <Button
                    size="sm"
                    variant="quiet"
                    className="mt-2 -ml-3 !text-ink-3 hover:!bg-danger-tint hover:!text-danger"
                    icon={<X className="size-4" aria-hidden />}
                    onClick={() => remove(here)}
                  >
                    Remove {current.name.trim() || "this app"}
                  </Button>
                </div>
              )}
            </Sheet>
          )}
        </div>
      </div>

      {dirty && (
        <SaveBar
          what="Unsaved changes to your apps"
          saving={saving}
          onSave={save}
          onDiscard={() => {
            setDraft(null);
            setError(null);
            setProblems({});
          }}
          error={<FormError message={error} />}
        />
      )}
    </>
  );
}
