"use client";

import { Megaphone, Pencil, Siren } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { declareIncident, postIncidentUpdate, updateIncident, type IncidentInput } from "@/src/actions/support";
import type { Incident, IncidentKind, IncidentSeverity, IncidentStatus, Options } from "@/src/lib/types";
import { INCIDENT_KINDS, INCIDENT_SEVERITIES, INCIDENT_STATUSES } from "@/src/lib/words";
import { fieldError, orNull } from "../support/errors";
import { PanelActions, PanelButton } from "../support/panel";

// Declaring an incident, changing what it says about itself, and moving it
// along with an update. Anyone on staff may do all three.

const KINDS = (Object.keys(INCIDENT_KINDS) as IncidentKind[]).map((k) => ({ value: k, label: INCIDENT_KINDS[k] }));
const SEVERITIES = (Object.keys(INCIDENT_SEVERITIES) as IncidentSeverity[]).map((s) => ({ value: s, label: INCIDENT_SEVERITIES[s] }));
const STATUSES = (Object.keys(INCIDENT_STATUSES) as IncidentStatus[]).map((s) => ({ value: s, label: INCIDENT_STATUSES[s].label }));

/** Ticks for the companies an incident reaches. None ticked is everyone. */
function CompanyTicks({ options, value, onChange, appName, error }: { options: Options["companies"]; value: string[]; onChange: (ids: string[]) => void; appName: string | null; error?: string }) {
  const [filter, setFilter] = useState("");
  const shown = options.filter((c) => c.name.toLowerCase().includes(filter.trim().toLowerCase()));
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1 text-meta font-medium text-ink-2">
        Companies it reaches <span className="font-normal text-ink-3">(optional)</span>
      </legend>
      <p className="mb-2 text-meta text-ink-3">
        {value.length === 0 ? `None ticked: it reaches ${appName ? `everyone on ${appName}` : "everyone on the platform"}.` : `${value.length} ticked.`}
      </p>
      {options.length > 8 && (
        <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Find a company" aria-label="Find a company" className="mb-2" />
      )}
      <div className="max-h-44 overflow-y-auto rounded-[18px] border border-rule px-3 py-1">
        {options.length === 0 ? (
          <p className="py-2 text-meta text-ink-3">No companies on the platform yet.</p>
        ) : (
          shown.map((c) => (
            <label key={c.id} className="flex cursor-pointer items-center gap-2 py-1 text-sm">
              <input type="checkbox" checked={value.includes(c.id)} onChange={() => toggle(c.id)} className="size-4 accent-[var(--color-hema)]" />
              {c.name}
              {c.status === "suspended" && <span className="text-meta text-ink-3">suspended</span>}
            </label>
          ))
        )}
      </div>
      {error && <p className="mt-1 text-meta text-danger">{error}</p>}
    </fieldset>
  );
}

function IncidentForm({ options, incident, onDone }: { options: Options; incident?: Incident; onDone: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [title, setTitle] = useState(incident?.title ?? "");
  const [kind, setKind] = useState<IncidentKind>(incident?.kind ?? "disruption");
  const [severity, setSeverity] = useState<IncidentSeverity>(incident?.severity ?? "major");
  const [applicationId, setApplicationId] = useState(incident?.application?.id ?? "");
  const [companyIds, setCompanyIds] = useState<string[]>(incident?.companies.map((c) => c.id) ?? []);
  const [leadId, setLeadId] = useState(incident?.lead?.id ?? "");
  const [summary, setSummary] = useState(incident?.summary ?? "");
  const [update, setUpdate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  // A retired application isn't offered, but one already named stays named.
  const apps = incident?.application && !options.applications.some((a) => a.id === incident.application!.id)
    ? [...options.applications, { ...incident.application, key: "" }]
    : options.applications;
  const appName = apps.find((a) => a.id === applicationId)?.name ?? null;

  function submit() {
    const input: IncidentInput = {
      title: title.trim(),
      kind,
      severity,
      applicationId: applicationId || null,
      companyIds,
      leadId: leadId || null,
      summary: orNull(summary),
    };
    start(async () => {
      if (incident) {
        // Only what changed: the API notes every field it's sent in the audit log.
        const was: IncidentInput = {
          title: incident.title,
          kind: incident.kind,
          severity: incident.severity,
          applicationId: incident.application?.id ?? null,
          companyIds: incident.companies.map((c) => c.id),
          leadId: incident.lead?.id ?? null,
          summary: incident.summary,
        };
        const same = (a: unknown, b: unknown) => JSON.stringify(Array.isArray(a) ? [...a].sort() : a ?? null) === JSON.stringify(Array.isArray(b) ? [...b].sort() : b ?? null);
        const patch = Object.fromEntries(Object.entries(input).filter(([k, v]) => !same(v, was[k as keyof IncidentInput])));
        if (Object.keys(patch).length === 0) return onDone();
        const result = await updateIncident(incident.id, patch);
        if (!result.ok) {
          setError(result.error);
          setFields(result.fields ?? {});
          return;
        }
        toast.success("Changes saved", { description: `${incident.number} ${input.title}` });
        onDone();
        return;
      }
      const result = await declareIncident({ ...input, update: orNull(update) });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Incident declared", { description: `${result.data.number} ${result.data.title}` });
      onDone();
      router.push(`/incidents/${result.data.id}`);
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
      <Field label="What's wrong" hint="Said plainly, as the people it reaches would put it." error={fieldError(fields, "title")}>
        {(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Orders can't be saved in the CRM" autoFocus />}
      </Field>
      <Choice name="incident-kind" legend="Kind" value={kind} onChange={setKind} options={KINDS} />
      <Choice name="incident-severity" legend="How bad" value={severity} onChange={setSeverity} options={SEVERITIES} />
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Application" optional error={fieldError(fields, "applicationId")}>
          {(p) => (
            <Select {...p} value={applicationId} onChange={(e) => setApplicationId(e.target.value)}>
              <option value="">The whole platform</option>
              {apps.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Lead" optional hint="Who is running it." error={fieldError(fields, "leadId")}>
          {(p) => (
            <Select {...p} value={leadId} onChange={(e) => setLeadId(e.target.value)}>
              <option value="">Nobody yet</option>
              {options.staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <CompanyTicks options={options.companies} value={companyIds} onChange={setCompanyIds} appName={appName} error={fieldError(fields, "companyIds")} />
      <Field label="Summary" optional hint="What's known, for staff." error={fieldError(fields, "summary")}>
        {(p) => <Textarea {...p} rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} />}
      </Field>
      {!incident && (
        <Field label="First update" optional hint="What the people it reaches are told. Left empty, the summary is used, or “We're looking into it.”" error={fieldError(fields, "update")}>
          {(p) => <Textarea {...p} rows={3} value={update} onChange={(e) => setUpdate(e.target.value)} />}
        </Field>
      )}
      <FormError message={error} />
      <PanelActions pending={pending} save={incident ? "Save changes" : "Declare it"} onCancel={onDone} />
    </form>
  );
}

export function DeclareIncident({ options }: { options: Options }) {
  return (
    <PanelButton label="Declare an incident" title="Declare an incident" variant="primary" icon={<Siren className="size-4" aria-hidden />} wide>
      {(close) => <IncidentForm options={options} onDone={close} />}
    </PanelButton>
  );
}

export function EditIncident({ incident, options }: { incident: Incident; options: Options }) {
  return (
    <PanelButton tool label={`Edit ${incident.number}`} title={`${incident.number}: what it says`} icon={<Pencil className="size-4" aria-hidden />} wide>
      {(close) => <IncidentForm options={options} incident={incident} onDone={close} />}
    </PanelButton>
  );
}

function UpdateForm({ incident, onDone }: { incident: Incident; onDone: () => void }) {
  const [pending, start] = useTransition();
  // Most updates move it one step on; the step it's at is one click away.
  const order = STATUSES.map((s) => s.value);
  const next = order[Math.min(order.indexOf(incident.status) + 1, order.length - 1)];
  const [status, setStatus] = useState<IncidentStatus>(incident.status === "resolved" ? "resolved" : next);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const reopening = incident.status === "resolved" && status !== "resolved";
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const result = await postIncidentUpdate(incident.id, status, body.trim());
          if (!result.ok) {
            setError(result.error);
            setFields(result.fields ?? {});
            return;
          }
          toast.success(status === incident.status ? "Update posted" : `Marked ${INCIDENT_STATUSES[status].label}`, { description: incident.number });
          onDone();
        });
      }}
      className="space-y-5"
    >
      <div>
        <Choice name="update-status" legend="Where it is now" value={status} onChange={setStatus} options={STATUSES} />
        <p className="mt-1.5 text-meta text-ink-3">
          {INCIDENT_STATUSES[status].what}
          {status === "resolved" && incident.status !== "resolved" && " Resolving it stamps when it ended."}
          {reopening && " This reopens it."}
        </p>
      </div>
      <Field label="What to tell people" hint="Posted on the incident's timeline, as the latest word on it." error={fieldError(fields, "body")}>
        {(p) => <Textarea {...p} rows={4} value={body} onChange={(e) => setBody(e.target.value)} autoFocus />}
      </Field>
      <FormError message={error} />
      <PanelActions pending={pending} save="Post the update" onCancel={onDone} />
    </form>
  );
}

export function PostUpdate({ incident }: { incident: Incident }) {
  return (
    <PanelButton label="Post an update" title={`Post an update on ${incident.number}`} variant="primary" icon={<Megaphone className="size-4" aria-hidden />}>
      {(close) => <UpdateForm incident={incident} onDone={close} />}
    </PanelButton>
  );
}
