"use client";

import { Archive, ArchiveRestore, Pencil, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Choice, Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { addApplication, updateApplication, type ApplicationPatch } from "@/src/actions/applications";
import type { Application } from "@/src/lib/types";
import { fieldError, orNull } from "../support/errors";
import { PanelActions, PanelButton } from "../support/panel";

// Registering an application, changing its details, retiring it, and
// declaring its status over what the check says. Platform Admins only; the
// screens don't draw these for Support.

type Details = { key: string; name: string; description: string; appUrl: string; apiUrl: string; healthUrl: string; version: string };

function ApplicationForm({ app, onDone }: { app?: Application; onDone: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [v, setV] = useState<Details>({
    key: app?.key ?? "",
    name: app?.name ?? "",
    description: app?.description ?? "",
    appUrl: app?.appUrl ?? "",
    apiUrl: app?.apiUrl ?? "",
    healthUrl: app?.healthUrl ?? "",
    version: app?.version ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (k: keyof Details) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });

  function submit() {
    const details = {
      name: v.name.trim(),
      description: orNull(v.description),
      appUrl: orNull(v.appUrl),
      apiUrl: orNull(v.apiUrl),
      healthUrl: orNull(v.healthUrl),
      version: orNull(v.version),
    };
    start(async () => {
      if (app) {
        const patch: ApplicationPatch = {};
        for (const k of Object.keys(details) as (keyof typeof details)[]) if ((details[k] ?? null) !== (app[k] ?? null)) (patch as Record<string, unknown>)[k] = details[k];
        if (Object.keys(patch).length === 0) return onDone();
        const result = await updateApplication(app.id, patch);
        if (!result.ok) {
          setError(result.error);
          setFields(result.fields ?? {});
          return;
        }
        toast.success("Changes saved", { description: details.name });
        onDone();
        return;
      }
      const result = await addApplication({ key: v.key.trim().toLowerCase(), ...details });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Application registered", { description: result.data.name });
      onDone();
      router.push(`/applications/${result.data.id}`);
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-5"
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Name" error={fieldError(fields, "name")}>
          {(p) => <Input {...p} value={v.name} onChange={set("name")} autoFocus required />}
        </Field>
        {app ? (
          <Field label="Key" hint="Set when it was registered; the other apps know it by this.">
            {(p) => <Input {...p} value={app.key} disabled />}
          </Field>
        ) : (
          <Field label="Key" hint="A short lower-case name like crm or hris." error={fieldError(fields, "key")}>
            {(p) => <Input {...p} value={v.key} onChange={set("key")} autoCapitalize="none" spellCheck={false} required />}
          </Field>
        )}
      </div>
      <Field label="What it's for" optional error={fieldError(fields, "description")}>
        {(p) => <Textarea {...p} rows={2} value={v.description} onChange={set("description")} />}
      </Field>
      <Field label="Where people open it" optional hint="The address of its screens." error={fieldError(fields, "appUrl")}>
        {(p) => <Input {...p} type="url" inputMode="url" placeholder="https://" value={v.appUrl} onChange={set("appUrl")} />}
      </Field>
      <Field label="Its API" optional hint="Where the applications linked to it call it (Connections), e.g. https://crm-api.example.com." error={fieldError(fields, "apiUrl")}>
        {(p) => <Input {...p} type="url" inputMode="url" placeholder="https://" value={v.apiUrl} onChange={set("apiUrl")} />}
      </Field>
      <Field
        label="Health address"
        optional
        hint="Its API's /health. The platform asks this address itself whether the app is up and how fast it answers, so nobody has to report it. Without one, it shows as not checked."
        error={fieldError(fields, "healthUrl")}
      >
        {(p) => <Input {...p} type="url" inputMode="url" placeholder="https://…/health" value={v.healthUrl} onChange={set("healthUrl")} />}
      </Field>
      <Field label="Version" optional hint={app ? "Recording a production deployment sets this for you." : undefined} error={fieldError(fields, "version")}>
        {(p) => <Input {...p} value={v.version} onChange={set("version")} className="max-w-[12rem]" />}
      </Field>
      <FormError message={error} />
      <PanelActions pending={pending} save={app ? "Save changes" : "Register it"} onCancel={onDone} />
    </form>
  );
}

export function RegisterApplication() {
  return (
    <PanelButton label="Register an application" title="Register an application" variant="primary" icon={<Plus className="size-4" aria-hidden />} wide>
      {(close) => <ApplicationForm onDone={close} />}
    </PanelButton>
  );
}

export function EditApplication({ app }: { app: Application }) {
  return (
    <PanelButton tool label={`Edit ${app.name}'s details`} title={`${app.name}: details`} icon={<Pencil className="size-4" aria-hidden />} wide>
      {(close) => <ApplicationForm app={app} onDone={close} />}
    </PanelButton>
  );
}

/** Retiring takes it out of use; restoring puts it back. Both ask first. */
export function RetireApplication({ app }: { app: Application }) {
  const retiring = app.isActive;
  return (
    <ConfirmButton
      label={<span className="sr-only">{retiring ? `Retire ${app.name}` : `Restore ${app.name}`}</span>}
      icon={retiring ? <Archive className="size-4" aria-hidden /> : <ArchiveRestore className="size-4" aria-hidden />}
      triggerTitle={retiring ? `Retire ${app.name}` : `Restore ${app.name}`}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName={`!size-8 !px-0 !text-ink-3 ${retiring ? "hover:!bg-danger/10 hover:!text-danger" : "hover:!bg-hema-tint hover:!text-hema"}`}
      danger={retiring}
      title={retiring ? `Retire ${app.name}?` : `Restore ${app.name}?`}
      body={
        retiring
          ? "The platform stops checking it, and it leaves the registry, monitoring and the pickers for tickets and incidents. Its deployments, checks and tickets are kept, and you can restore it."
          : "It comes back into the registry and monitoring, and the platform starts checking its health address again."
      }
      confirmLabel={retiring ? "Retire it" : "Restore it"}
      onConfirm={async () => {
        const result = await updateApplication(app.id, { isActive: !retiring });
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(retiring ? "Retired" : "Restored", { description: app.name });
      }}
    />
  );
}

type Override = NonNullable<Application["statusOverride"]>;
const OVERRIDES: { value: Override; label: string; what: string }[] = [
  { value: "maintenance", label: "Maintenance", what: "Planned work: people may not be able to use it for a while." },
  { value: "degraded", label: "Degraded", what: "It works, but slowly or with parts missing." },
  { value: "outage", label: "Outage", what: "It isn't working, whatever the check says." },
];

function DeclareForm({ app, onDone }: { app: Application; onDone: () => void }) {
  const [pending, start] = useTransition();
  const [status, setStatus] = useState<Override>(app.statusOverride ?? "maintenance");
  const [note, setNote] = useState(app.statusNote ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const result = await updateApplication(app.id, { statusOverride: status, statusNote: orNull(note) });
          if (!result.ok) {
            setError(result.error);
            setFields(result.fields ?? {});
            return;
          }
          toast.success(`${app.name} marked ${OVERRIDES.find((o) => o.value === status)!.label.toLowerCase()}`);
          onDone();
        });
      }}
      className="space-y-5"
    >
      <p className="text-sm text-ink-2">
        What you declare is what every screen shows for {app.name}, over what its health check says, until you set it back.
      </p>
      <div>
        <Choice<Override> name="override" legend="Status" value={status} onChange={setStatus} options={OVERRIDES} />
        <p className="mt-1.5 text-meta text-ink-3">{OVERRIDES.find((o) => o.value === status)!.what}</p>
      </div>
      <Field label="Note" optional hint="Shown beside the status: what's happening, and until when." error={fieldError(fields, "statusNote")}>
        {(p) => <Textarea {...p} rows={2} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} />}
      </Field>
      <FormError message={error} />
      <PanelActions pending={pending} save="Declare it" onCancel={onDone} />
    </form>
  );
}

export function DeclareStatus({ app }: { app: Application }) {
  return (
    <PanelButton label={app.statusOverride ? "Change the declared status" : "Declare a status"} title={`Declare ${app.name}'s status`}>
      {(close) => <DeclareForm app={app} onDone={close} />}
    </PanelButton>
  );
}

export function BackToCheck({ app }: { app: Application }) {
  return (
    <AsyncButton
      size="sm"
      variant="quiet"
      onRun={async () => {
        const result = await updateApplication(app.id, { statusOverride: null });
        if (!result.ok) toast.error(result.error);
        else toast.success(`${app.name} shows what its check says again`);
      }}
    >
      Back to what the check says
    </AsyncButton>
  );
}
