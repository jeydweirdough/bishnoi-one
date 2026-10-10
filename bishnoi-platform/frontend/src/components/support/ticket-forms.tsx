"use client";

import { Pencil, Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { addTicket, addTicketNote, updateTicket, type TicketInput } from "@/src/actions/support";
import type { Options, Severity, Ticket, TicketKind } from "@/src/lib/types";
import { SEVERITIES, TICKET_KINDS } from "@/src/lib/words";
import { fieldError, orNull } from "./errors";
import { findUsers, type Found } from "./find-users";
import { PanelActions, PanelButton } from "./panel";

// Logging a ticket, changing its words, and adding a note to it. Anyone on
// staff works tickets.

export const KIND_OPTIONS = (Object.keys(TICKET_KINDS) as TicketKind[]).map((k) => ({ value: k, label: TICKET_KINDS[k].one }));
export const SEVERITY_OPTIONS = (Object.keys(SEVERITIES) as Severity[]).map((s) => ({ value: s, label: SEVERITIES[s] }));

/** Who reported it: somebody on the platform, found by name or email, or a name and email as they gave them. */
function Reporter({
  picked,
  onPick,
  name,
  email,
  onName,
  onEmail,
  errors,
}: {
  picked: Found | null;
  onPick: (person: Found | null) => void;
  name: string;
  email: string;
  onName: (v: string) => void;
  onEmail: (v: string) => void;
  errors: { name?: string; email?: string; picked?: string };
}) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Found[]>([]);
  const [looking, start] = useTransition();

  useEffect(() => {
    if (picked || q.trim().length < 2) return;
    const t = setTimeout(
      () =>
        start(async () => {
          const result = await findUsers(q);
          setFound(result.ok ? result.data : []);
        }),
      250,
    );
    return () => clearTimeout(t);
  }, [q, picked]);

  if (picked) {
    return (
      <div>
        <p className="mb-1 text-meta font-medium text-ink-2">Reported by</p>
        <p className="flex items-center justify-between gap-3 rounded-[14px] border border-rule px-3 py-2 text-sm">
          <span className="min-w-0">
            <b className="font-semibold">{picked.name}</b>
            <span className="text-ink-2">
              {" "}
              · {picked.email}
              {picked.companyName && ` · ${picked.companyName}`}
            </span>
          </span>
          <button type="button" onClick={() => onPick(null)} aria-label={`Not ${picked.name}`} title={`Not ${picked.name}`} className="rounded-full p-1 text-ink-3 hover:bg-bench hover:text-ink">
            <X className="size-4" aria-hidden />
          </button>
        </p>
      </div>
    );
  }

  return (
    <fieldset className="min-w-0 space-y-3">
      <legend className="mb-1 text-meta font-medium text-ink-2">Reported by</legend>
      <Field label="Find them on the platform" hint="By name or email. If they aren't on it, write their name or email below." error={errors.picked}>
        {(p) => <Input {...p} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or email" autoComplete="off" />}
      </Field>
      {q.trim().length >= 2 && (
        <div aria-live="polite" className="text-meta">
          {looking && found.length === 0 ? (
            <p className="text-ink-3">Looking…</p>
          ) : found.length === 0 ? (
            <p className="text-ink-3">Nobody on the platform matches. Write their name or email below.</p>
          ) : (
            <ul className="divide-y divide-rule rounded-[18px] border border-rule">
              {found.map((u) => (
                <li key={u.id}>
                  <button type="button" onClick={() => onPick(u)} className="w-full px-3 py-2 text-left hover:bg-hema-tint">
                    <span className="font-semibold text-ink">{u.name}</span>
                    <span className="text-ink-2">
                      {" "}
                      · {u.email}
                      {u.companyName && ` · ${u.companyName}`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Their name" optional error={errors.name}>
          {(p) => <Input {...p} value={name} onChange={(e) => onName(e.target.value)} />}
        </Field>
        <Field label="Their email" optional error={errors.email}>
          {(p) => <Input {...p} type="email" inputMode="email" value={email} onChange={(e) => onEmail(e.target.value)} />}
        </Field>
      </div>
    </fieldset>
  );
}

function TicketForm({ options, onDone }: { options: Options; onDone: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [kind, setKind] = useState<TicketKind>("bug");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [picked, setPicked] = useState<Found | null>(null);
  const [reporterName, setReporterName] = useState("");
  const [reporterEmail, setReporterEmail] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [applicationId, setApplicationId] = useState("");
  const [affected, setAffected] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  function pick(person: Found | null) {
    setPicked(person);
    // Their company is the likeliest one; it can still be changed.
    if (person && !companyId) setCompanyId(person.companyId);
  }

  function submit() {
    const input: TicketInput = {
      kind,
      title: title.trim(),
      description: orNull(description),
      severity,
      identityId: picked?.id ?? null,
      reporterName: picked ? null : orNull(reporterName),
      reporterEmail: picked ? null : orNull(reporterEmail),
      companyId: companyId || null,
      applicationId: applicationId || null,
      affectedUsers: affected.trim() === "" ? null : Number(affected),
      assigneeId: assigneeId || null,
    };
    start(async () => {
      const result = await addTicket(input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Ticket logged", { description: `${result.data.number} ${result.data.title}` });
      onDone();
      router.push(`/support/${result.data.id}`);
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
      <div>
        <Choice name="ticket-kind" legend="Kind" value={kind} onChange={setKind} options={KIND_OPTIONS} />
        <p className="mt-1.5 text-meta text-ink-3">{TICKET_KINDS[kind].what}</p>
      </div>
      <Field label="Title" hint="What's wrong or wanted, in a line." error={fieldError(fields, "title")}>
        {(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />}
      </Field>
      <Field label="What they said" optional hint="Steps, what they expected, what happened." error={fieldError(fields, "description")}>
        {(p) => <Textarea {...p} rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />}
      </Field>
      <Choice name="ticket-severity" legend="Severity" value={severity} onChange={setSeverity} options={SEVERITY_OPTIONS} />
      <Reporter
        picked={picked}
        onPick={pick}
        name={reporterName}
        email={reporterEmail}
        onName={setReporterName}
        onEmail={setReporterEmail}
        errors={{ name: fieldError(fields, "reporterName"), email: fieldError(fields, "reporterEmail"), picked: fieldError(fields, "identityId") }}
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Company" optional error={fieldError(fields, "companyId")}>
          {(p) => (
            <Select {...p} value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
              <option value="">None</option>
              {options.companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Application" optional error={fieldError(fields, "applicationId")}>
          {(p) => (
            <Select {...p} value={applicationId} onChange={(e) => setApplicationId(e.target.value)}>
              <option value="">None in particular</option>
              {options.applications.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="People affected" optional error={fieldError(fields, "affectedUsers")}>
          {(p) => <Input {...p} type="number" inputMode="numeric" min={0} value={affected} onChange={(e) => setAffected(e.target.value)} />}
        </Field>
        <Field label="Assign to" optional hint="Assigning it marks it Assigned." error={fieldError(fields, "assigneeId")}>
          {(p) => (
            <Select {...p} value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
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
      <FormError message={error} />
      <PanelActions pending={pending} save="Log it" onCancel={onDone} />
    </form>
  );
}

export function LogTicket({ options }: { options: Options }) {
  return (
    <PanelButton label="Log a ticket" title="Log a ticket" variant="primary" icon={<Plus className="size-4" aria-hidden />} wide>
      {(close) => <TicketForm options={options} onDone={close} />}
    </PanelButton>
  );
}

function WordsForm({ ticket, onDone }: { ticket: Ticket; onDone: () => void }) {
  const [pending, start] = useTransition();
  const [title, setTitle] = useState(ticket.title);
  const [description, setDescription] = useState(ticket.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        const patch: { title?: string; description?: string | null } = {};
        if (title.trim() !== ticket.title) patch.title = title.trim();
        if (orNull(description) !== (ticket.description ?? null)) patch.description = orNull(description);
        if (Object.keys(patch).length === 0) return onDone();
        start(async () => {
          const result = await updateTicket(ticket.id, patch);
          if (!result.ok) {
            setError(result.error);
            setFields(result.fields ?? {});
            return;
          }
          toast.success("Changes saved", { description: ticket.number });
          onDone();
        });
      }}
      className="space-y-5"
    >
      <Field label="Title" error={fieldError(fields, "title")}>
        {(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />}
      </Field>
      <Field label="What they said" optional error={fieldError(fields, "description")}>
        {(p) => <Textarea {...p} rows={6} value={description} onChange={(e) => setDescription(e.target.value)} />}
      </Field>
      <FormError message={error} />
      <PanelActions pending={pending} save="Save changes" onCancel={onDone} />
    </form>
  );
}

export function EditTicketWords({ ticket }: { ticket: Ticket }) {
  return (
    <PanelButton tool label={`Edit the title and description of ${ticket.number}`} title={`${ticket.number}: title and description`} icon={<Pencil className="size-4" aria-hidden />} wide>
      {(close) => <WordsForm ticket={ticket} onDone={close} />}
    </PanelButton>
  );
}

export function AddNote({ ticketId }: { ticketId: string }) {
  const [pending, start] = useTransition();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (!body.trim()) return setError("Write the note first.");
        start(async () => {
          const result = await addTicketNote(ticketId, body.trim());
          if (!result.ok) return setError(result.error);
          setBody("");
          setError(null);
          toast.success("Note added");
        });
      }}
      className="space-y-3 border-t border-rule pt-4"
    >
      <Field label="Add a note" hint="Kept on the ticket for whoever picks it up next." error={error ?? undefined}>
        {(p) => <Textarea {...p} rows={3} value={body} onChange={(e) => setBody(e.target.value)} />}
      </Field>
      <Button type="submit" size="sm" loading={pending}>
        Add the note
      </Button>
    </form>
  );
}
