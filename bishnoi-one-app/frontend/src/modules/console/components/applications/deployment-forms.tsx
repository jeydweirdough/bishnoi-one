"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/modules/console/platform/ui/confirm";
import { Choice, Field, FormError, Input, Textarea } from "@/src/modules/console/platform/ui/field";
import { addDeployment, addIntegration, deleteIntegration, updateIntegration, type IntegrationInput } from "@/src/modules/console/actions/applications";
import type { Deployment, Integration } from "@/src/modules/console/lib/types";
import { HEALTH } from "@/src/modules/console/lib/words";
import { fieldError, orNull } from "@/src/modules/console/components/support/errors";
import { PanelActions, PanelButton } from "@/src/modules/console/components/support/panel";

// An application's deployments and integrations: recording a release, and
// adding, changing and removing what it connects to. Platform Admins only.

const ENVIRONMENTS: { value: Deployment["environment"]; label: string }[] = [
  { value: "production", label: "Production" },
  { value: "staging", label: "Staging" },
  { value: "development", label: "Development" },
];

function DeploymentForm({ appId, appName, onDone }: { appId: string; appName: string; onDone: () => void }) {
  const [pending, start] = useTransition();
  const [version, setVersion] = useState("");
  const [environment, setEnvironment] = useState<Deployment["environment"]>("production");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const result = await addDeployment(appId, { version: version.trim(), environment, notes: orNull(notes) });
          if (!result.ok) {
            setError(result.error);
            setFields(result.fields ?? {});
            return;
          }
          toast.success("Deployment recorded", { description: `${appName} ${version.trim()}` });
          onDone();
        });
      }}
      className="space-y-5"
    >
      <Field label="Version" error={fieldError(fields, "version")}>
        {(p) => <Input {...p} value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2.4.0" autoFocus className="max-w-[12rem]" />}
      </Field>
      <div>
        <Choice name="environment" legend="Environment" value={environment} onChange={setEnvironment} options={ENVIRONMENTS} />
        <p className="mt-1.5 text-meta text-ink-3">
          {environment === "production"
            ? `Sets the current version of ${appName}.`
            : "Recorded only; the current version does not change."}
        </p>
      </div>
      <Field label="Release notes" optional error={fieldError(fields, "notes")}>
        {(p) => <Textarea {...p} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />}
      </Field>
      <FormError message={error} />
      <PanelActions pending={pending} save="Record deployment" onCancel={onDone} />
    </form>
  );
}

export function RecordDeployment({ appId, appName }: { appId: string; appName: string }) {
  return (
    <PanelButton label="Record deployment" title={`Record a deployment of ${appName}`} size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />}>
      {(close) => <DeploymentForm appId={appId} appName={appName} onDone={close} />}
    </PanelButton>
  );
}

type LinkStatus = Integration["status"];
const LINK_STATUSES: { value: LinkStatus; label: string }[] = (["operational", "degraded", "down", "unknown"] as const).map((s) => ({
  value: s,
  label: HEALTH[s],
}));

function IntegrationForm({ appId, link, onDone }: { appId: string; link?: Integration; onDone: () => void }) {
  const [pending, start] = useTransition();
  const [name, setName] = useState(link?.name ?? "");
  const [target, setTarget] = useState(link?.target ?? "");
  const [healthUrl, setHealthUrl] = useState(link?.healthUrl ?? "");
  const [status, setStatus] = useState<LinkStatus>(link?.status ?? "unknown");
  const [notes, setNotes] = useState(link?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const checked = healthUrl.trim() !== "";

  function submit() {
    const input: IntegrationInput = { name: name.trim(), target: orNull(target), healthUrl: orNull(healthUrl), notes: orNull(notes) };
    // With a health address, its status is what the check says.
    if (!checked) input.status = status;
    start(async () => {
      let result;
      if (link) {
        const patch: Partial<IntegrationInput> = {};
        for (const k of Object.keys(input) as (keyof IntegrationInput)[]) if ((input[k] ?? null) !== (link[k] ?? null)) (patch as Record<string, unknown>)[k] = input[k];
        if (Object.keys(patch).length === 0) return onDone();
        result = await updateIntegration(link.id, patch);
      } else {
        result = await addIntegration(appId, input);
      }
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(link ? "Changes saved" : "Integration added", { description: input.name });
      onDone();
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
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="Payments" autoFocus />}
        </Field>
        <Field label="Target" optional hint="A service, host or partner." error={fieldError(fields, "target")}>
          {(p) => <Input {...p} value={target} onChange={(e) => setTarget(e.target.value)} />}
        </Field>
      </div>
      <Field
        label="Health check URL"
        optional
        hint="With one, the platform monitors it and sets its status from the check. Without one, the status is set manually."
        error={fieldError(fields, "healthUrl")}
      >
        {(p) => <Input {...p} type="url" inputMode="url" placeholder="https://" value={healthUrl} onChange={(e) => setHealthUrl(e.target.value)} />}
      </Field>
      {!checked && <Choice name="link-status" legend="Status" value={status} onChange={setStatus} options={LINK_STATUSES} />}
      <Field label="Notes" optional error={fieldError(fields, "notes")}>
        {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}
      </Field>
      <FormError message={error} />
      <PanelActions pending={pending} save={link ? "Save changes" : "Add integration"} onCancel={onDone} />
    </form>
  );
}

export function AddIntegration({ appId, appName }: { appId: string; appName: string }) {
  return (
    <PanelButton label="Add integration" title={`Add an integration to ${appName}`} size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />}>
      {(close) => <IntegrationForm appId={appId} onDone={close} />}
    </PanelButton>
  );
}

export function EditIntegration({ link }: { link: Integration }) {
  return (
    <PanelButton tool label={`Edit the ${link.name} integration`} title={`The ${link.name} integration`} icon={<Pencil className="size-4" aria-hidden />}>
      {(close) => <IntegrationForm appId={link.applicationId} link={link} onDone={close} />}
    </PanelButton>
  );
}

export function RemoveIntegration({ link }: { link: Integration }) {
  return (
    <ConfirmButton
      label={<span className="sr-only">Remove the {link.name} integration</span>}
      icon={<Trash2 className="size-4" aria-hidden />}
      triggerTitle={`Remove the ${link.name} integration`}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName="!size-8 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
      title={`Remove the ${link.name} integration?`}
      body="It is removed from the application's record and from monitoring. This can't be undone."
      confirmLabel="Remove"
      onConfirm={async () => {
        const result = await deleteIntegration(link.id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success("Integration removed", { description: link.name });
      }}
    />
  );
}
