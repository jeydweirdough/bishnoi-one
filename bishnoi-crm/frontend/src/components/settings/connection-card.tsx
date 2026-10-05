"use client";

import { Input as AntInput, Switch, Tag } from "antd";
import { ExternalLink } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { checkConnection, saveConnection, type ConnectionInfo } from "../../actions/settings";

type Props = { connection: ConnectionInfo; checkedWhen: string | null; updatedWhen: string | null };

/** Where a connection stands, in words: switched on or off, and how its last test went. */
function Status({ c }: { c: ConnectionInfo }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      <Tag color={c.enabled ? "processing" : "default"}>{c.enabled ? "Switched on" : "Switched off"}</Tag>
      {c.missing.length > 0 ? (
        <Tag>Details needed</Tag>
      ) : !c.check ? (
        <Tag>Not tested</Tag>
      ) : c.check.ok ? (
        <Tag color="success">Tested: working</Tag>
      ) : (
        <Tag color="error">Tested: not working</Tag>
      )}
    </span>
  );
}

/** One service: what it's for, its details (secrets masked), Save, Test and the switch. */
export function ConnectionCard({ connection: c, checkedWhen, updatedWhen }: Props) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, startSave] = useTransition();
  const [testing, startTest] = useTransition();
  const dirty = Object.keys(draft).length > 0;
  const set = (key: string, value: string) => setDraft((d) => ({ ...d, [key]: value }));

  function save(enabled?: boolean) {
    startSave(async () => {
      const r = await saveConnection(c.key, draft, enabled);
      if (!r.ok) {
        setError(r.fields ? null : r.error);
        setFields(r.fields ?? {});
        return;
      }
      setDraft({});
      setFields({});
      setError(null);
      toast.success(enabled === undefined ? "Saved" : enabled ? `${c.name} switched on` : `${c.name} switched off`);
    });
  }

  function test() {
    startTest(async () => {
      const r = await checkConnection(c.key);
      if (!r.ok) return setError(r.error);
      setError(null);
      if (r.data.check?.ok) toast.success(r.data.check.message);
      else toast.error("It didn't work", { description: r.data.check?.message });
    });
  }

  return (
    <Sheet className="px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-ink">{c.name}</h2>
          <p className="mt-0.5 text-sm text-ink-2">{c.purpose}</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink">
          <Switch checked={c.enabled} loading={saving} onChange={(on) => save(on)} disabled={dirty} />
          {c.enabled ? "On" : "Off"}
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <Status c={c} />
        <a href={c.helpUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-meta text-ink underline-offset-2 hover:underline">
          Where to find these <ExternalLink className="size-3" aria-hidden />
        </a>
      </div>
      {c.check && (
        <p className="mt-2 text-meta text-ink-3">
          Last test {checkedWhen}: {c.check.message}
        </p>
      )}

      <form
        noValidate
        className="mt-5 grid gap-5 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        {c.details.map((d) => {
          const typed = draft[d.key];
          if (d.options.length > 0) {
            return (
              <Field key={d.key} label={d.label} hint={d.hint} error={fields[d.key]} optional={!d.required}>
                {(p) => (
                  <Select {...p} value={typed ?? d.value ?? ""} onChange={(e) => set(d.key, e.target.value)}>
                    <option value="">Pick one</option>
                    {d.options.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            );
          }
          if (d.secret) {
            const removing = typed === "" && d.saved;
            return (
              <Field key={d.key} label={d.label} hint={d.hint} error={fields[d.key]} optional={!d.required}>
                {(p) => (
                  <div className="space-y-1">
                    <AntInput.Password
                      id={p.id}
                      aria-describedby={p["aria-describedby"]}
                      status={fields[d.key] ? "error" : undefined}
                      value={typed ?? ""}
                      onChange={(e) => set(d.key, e.target.value)}
                      autoComplete="new-password"
                      placeholder={removing ? "Will be removed when you save" : d.saved ? `Saved${d.ending ? `, ends in ${d.ending}` : ""}. Type to replace.` : "Not saved yet"}
                    />
                    {d.saved && !removing && (
                      <button type="button" className="text-meta text-ink-3 hover:text-ink hover:underline" onClick={() => set(d.key, "")}>
                        Remove the saved {d.label.toLowerCase()}
                      </button>
                    )}
                  </div>
                )}
              </Field>
            );
          }
          return (
            <Field key={d.key} label={d.label} hint={d.hint} error={fields[d.key]} optional={!d.required}>
              {(p) => <Input {...p} value={typed ?? d.value ?? ""} onChange={(e) => set(d.key, e.target.value)} autoComplete="off" />}
            </Field>
          );
        })}
        {error && (
          <div className="sm:col-span-2">
            <FormError message={error} />
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
          <Button type="submit" variant="primary" loading={saving} disabled={!dirty}>
            Save
          </Button>
          <Button onClick={test} loading={testing} disabled={dirty || c.missing.length > 0}>
            Test connection
          </Button>
          {dirty && (
            <Button variant="quiet" onClick={() => setDraft({})}>
              Undo changes
            </Button>
          )}
          {updatedWhen && c.updatedBy && (
            <span className="ml-auto text-meta text-ink-3">
              Changed {updatedWhen} by {c.updatedBy.name}
            </span>
          )}
        </div>
      </form>
    </Sheet>
  );
}
