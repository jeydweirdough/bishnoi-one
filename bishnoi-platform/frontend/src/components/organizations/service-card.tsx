"use client";

import { ExternalLink } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { checkService, saveService, type ServiceInfo } from "../../actions/services";

const APP_NAMES: Record<string, string> = { crm: "the CRM", inventory: "Inventory", finance: "Finance", pharmacy: "Pharmacy" };

/** A stamp beside the name: on or off, and how its last test went. */
function Stamp({ children, tone = "plain" }: { children: string; tone?: "plain" | "good" | "bad" }) {
  const look = tone === "good" ? "border-hema text-hema" : tone === "bad" ? "border-danger text-danger" : "border-ink-2 text-ink-2";
  return <span className={`inline-flex h-5 shrink-0 items-center rounded-[2px] border px-1.5 text-stamp whitespace-nowrap uppercase ${look}`}>{children}</span>;
}

type Props = { companyId: string; service: ServiceInfo; canChange: boolean; checkedWhen: string | null; updatedWhen: string | null };

/**
 * One outside service for one company: what it's for, which application uses
 * it, its details (secrets masked once saved), Save, Test and on/off. The
 * applications are given what's here; nothing is kept on their servers.
 */
export function ServiceCard({ companyId, service: s, canChange, checkedWhen, updatedWhen }: Props) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, startSave] = useTransition();
  const [testing, startTest] = useTransition();
  const dirty = Object.keys(draft).length > 0;
  const set = (key: string, value: string) => setDraft((d) => ({ ...d, [key]: value }));
  const usedBy = s.apps.map((a) => APP_NAMES[a] ?? a).join(" and ");

  function save(enabled?: boolean) {
    startSave(async () => {
      const r = await saveService(companyId, s.key, draft, enabled);
      if (!r.ok) {
        setError(r.fields ? null : r.error);
        setFields(r.fields ?? {});
        return;
      }
      setDraft({});
      setFields({});
      setError(null);
      toast.success(enabled === undefined ? "Saved" : enabled ? `${s.name} switched on` : `${s.name} switched off`);
    });
  }

  function test() {
    startTest(async () => {
      const r = await checkService(companyId, s.key);
      if (!r.ok) return setError(r.error);
      setError(null);
      if (r.data.check?.ok) toast.success(r.data.check.message);
      else toast.error("It didn't work", { description: r.data.check?.message });
    });
  }

  return (
    <Sheet className="px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-heading text-ink">{s.name}</h3>
          <p className="mt-0.5 text-sm text-ink-2">{s.purpose}</p>
          <p className="mt-0.5 text-meta text-ink-3">Used by {usedBy}.</p>
        </div>
        <span className="flex flex-wrap items-center gap-1.5">
          <Stamp tone={s.enabled ? "good" : "plain"}>{s.enabled ? "On" : "Off"}</Stamp>
          {s.unreadable ? (
            <Stamp tone="bad">Type the secrets again</Stamp>
          ) : s.missing.length > 0 ? (
            <Stamp>Details needed</Stamp>
          ) : !s.check ? (
            <Stamp>Not tested</Stamp>
          ) : s.check.ok ? (
            <Stamp tone="good">Working</Stamp>
          ) : (
            <Stamp tone="bad">Not working</Stamp>
          )}
        </span>
      </div>
      {s.unreadable && (
        <p className="mt-2 text-meta text-danger">The platform&apos;s signing key changed since these were saved, so the secrets can&apos;t be read. Type them in again.</p>
      )}
      {s.check && (
        <p className="mt-2 text-meta text-ink-3">
          Last test {checkedWhen}: {s.check.message}
        </p>
      )}
      <a href={s.helpUrl} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-meta text-hema hover:underline">
        Where to find these <ExternalLink className="size-3" aria-hidden />
      </a>

      <form
        noValidate
        className="mt-4 grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <fieldset disabled={!canChange} className="contents">
          {s.details.map((d) => {
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
                      <Input
                        {...p}
                        type="password"
                        value={typed ?? ""}
                        onChange={(e) => set(d.key, e.target.value)}
                        autoComplete="new-password"
                        placeholder={removing ? "Removed when you save" : d.saved ? `Saved${d.ending ? `, ends in ${d.ending}` : ""}. Type to replace.` : "Not saved yet"}
                      />
                      {canChange && d.saved && !removing && (
                        <button type="button" className="text-meta text-ink-3 hover:text-danger hover:underline" onClick={() => set(d.key, "")}>
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
        </fieldset>
        {error && (
          <div className="sm:col-span-2">
            <FormError message={error} />
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
          {canChange && (
            <>
              <Button type="submit" variant="primary" size="sm" loading={saving} disabled={!dirty}>
                Save
              </Button>
              <Button size="sm" onClick={test} loading={testing} disabled={dirty || s.missing.length > 0 || s.unreadable}>
                Test connection
              </Button>
              <Button size="sm" variant={s.enabled ? "default" : "quiet"} onClick={() => save(!s.enabled)} disabled={dirty || saving}>
                {s.enabled ? "Switch off" : "Switch on"}
              </Button>
              {dirty && (
                <Button size="sm" variant="quiet" onClick={() => setDraft({})}>
                  Undo changes
                </Button>
              )}
            </>
          )}
          {updatedWhen && s.updatedBy && (
            <span className="ml-auto text-meta text-ink-3">
              Changed {updatedWhen} by {s.updatedBy.name}
            </span>
          )}
        </div>
      </form>
    </Sheet>
  );
}
