"use client";

import { Pencil } from "lucide-react";
import Link from "next/link";
import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Flag } from "@/src/platform/ui/marks";
import { Particulars } from "@/src/platform/ui/sheet";
import { updateTicket, type TicketPatch } from "@/src/actions/support";
import { KindMark, SeverityMark, TicketStatusMark } from "@/src/components/marks";
import type { Options, Ref, Severity, TicketDetail, TicketKind, TicketStatus } from "@/src/lib/types";
import { TICKET_STATUSES, ago, when } from "@/src/lib/words";
import { PanelActions, PanelButton } from "./panel";
import { KIND_OPTIONS, SEVERITY_OPTIONS } from "./ticket-forms";

// A ticket's particulars, each with the way to change it beside it: its
// status, who has it, how bad it is, what it's about.

type Render<T> = (value: T, set: (v: T) => void, error?: string) => ReactNode;

/** One field's editor: a pencil beside the value, opening a panel with just that field. */
function Change<T>({ ticketId, what, initial, patch, children }: { ticketId: string; what: string; initial: T; patch: (value: T) => TicketPatch; children: Render<T> }) {
  return (
    <PanelButton tool label={`Change ${what}`} title={`Change ${what}`} icon={<Pencil className="size-3.5" aria-hidden />}>
      {(close) => <ChangeForm ticketId={ticketId} initial={initial} patch={patch} onDone={close} render={children} />}
    </PanelButton>
  );
}

function ChangeForm<T>({ ticketId, initial, patch, onDone, render }: { ticketId: string; initial: T; patch: (value: T) => TicketPatch; onDone: () => void; render: Render<T> }) {
  const [value, setValue] = useState<T>(initial);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fieldMessage, setFieldMessage] = useState<string | undefined>();
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const result = await updateTicket(ticketId, patch(value));
          if (!result.ok) {
            // One field on the form: whichever field the API names is this one.
            const named = Object.values(result.fields ?? {})[0];
            setFieldMessage(named);
            setError(named ? null : result.error);
            return;
          }
          toast.success("Saved");
          onDone();
        });
      }}
      className="space-y-5"
    >
      {render(value, setValue, fieldMessage)}
      <FormError message={error} />
      <PanelActions pending={pending} save="Save" onCancel={onDone} />
    </form>
  );
}

/** A value with its editor beside it. */
function Row({ children, editor }: { children: ReactNode; editor: ReactNode }) {
  return (
    <span className="-my-1.5 flex min-h-8 items-center justify-between gap-2">
      <span className="min-w-0">{children}</span>
      {editor}
    </span>
  );
}

/** A picker's choices, keeping the current one even when it's no longer offered (a resolved incident, a retired app). */
function withCurrent(list: Ref[], current: Ref | null): Ref[] {
  return current && !list.some((r) => r.id === current.id) ? [current, ...list] : list;
}

function RefSelect({ label, value, set, list, none, error, hint }: { label: string; value: string; set: (v: string) => void; list: Ref[]; none: string; error?: string; hint?: string }) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(p) => (
        <Select {...p} value={value} onChange={(e) => set(e.target.value)} autoFocus>
          <option value="">{none}</option>
          {list.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

const STATUS_LIST = Object.keys(TICKET_STATUSES) as TicketStatus[];

export function TicketFields({ ticket, options }: { ticket: TicketDetail; options: Options }) {
  const n = ticket.number;
  const id = ticket.id;
  const link = (href: string, name: string) => (
    <Link href={href} className="text-hema hover:underline">
      {name}
    </Link>
  );

  return (
    <Particulars
      items={[
        [
          "Status",
          <Row
            key="status"
            editor={
              <Change<{ status: TicketStatus; note: string }>
                ticketId={id}
                what={`the status of ${n}`}
                initial={{ status: ticket.status, note: "" }}
                patch={(v) => ({ status: v.status, note: v.note.trim() || null })}
              >
                {(v, set, error) => (
                  <>
                    <Field label="New status" hint="Any status; steps can be skipped, and a closed ticket can be reopened." error={error}>
                      {(p) => (
                        <Select {...p} value={v.status} onChange={(e) => set({ ...v, status: e.target.value as TicketStatus })} autoFocus>
                          {STATUS_LIST.map((s) => (
                            <option key={s} value={s}>
                              {TICKET_STATUSES[s]}
                              {s === ticket.status ? " (now)" : ""}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                    <Field label="Reason" optional hint="Saved on the ticket with the status change.">
                      {(p) => <Textarea {...p} rows={3} value={v.note} onChange={(e) => set({ ...v, note: e.target.value })} />}
                    </Field>
                  </>
                )}
              </Change>
            }
          >
            <TicketStatusMark status={ticket.status} />
          </Row>,
        ],
        [
          "Assigned to",
          <Row
            key="assignee"
            editor={
              <Change<string> ticketId={id} what={`who has ${n}`} initial={ticket.assignee?.id ?? ""} patch={(v) => ({ assigneeId: v || null })}>
                {(v, set, error) => (
                  <RefSelect
                    label="Assign to"
                    value={v}
                    set={set}
                    list={withCurrent(options.staff, ticket.assignee)}
                    none="Unassigned"
                    error={error}
                    hint={ticket.status === "reported" || ticket.status === "triaged" ? "Assigning it sets the status to Assigned." : undefined}
                  />
                )}
              </Change>
            }
          >
            {ticket.assignee?.name ?? <span className="text-ink-3">Unassigned</span>}
          </Row>,
        ],
        [
          "Severity",
          <Row
            key="severity"
            editor={
              <Change<Severity> ticketId={id} what={`the severity of ${n}`} initial={ticket.severity} patch={(v) => ({ severity: v })}>
                {(v, set) => <Choice name="severity" legend="Severity" value={v} onChange={set} options={SEVERITY_OPTIONS} />}
              </Change>
            }
          >
            <SeverityMark severity={ticket.severity} />
          </Row>,
        ],
        [
          "Type",
          <Row
            key="kind"
            editor={
              <Change<TicketKind> ticketId={id} what={`what kind of ticket ${n} is`} initial={ticket.kind} patch={(v) => ({ kind: v })}>
                {(v, set) => <Choice name="kind" legend="Type" value={v} onChange={set} options={KIND_OPTIONS} />}
              </Change>
            }
          >
            <KindMark kind={ticket.kind} />
          </Row>,
        ],
        [
          "Company",
          <Row
            key="company"
            editor={
              <Change<string> ticketId={id} what={`the company on ${n}`} initial={ticket.company?.id ?? ""} patch={(v) => ({ companyId: v || null })}>
                {(v, set, error) => <RefSelect label="Company" value={v} set={set} list={withCurrent(options.companies, ticket.company)} none="None" error={error} />}
              </Change>
            }
          >
            {ticket.company ? link(`/companies/${ticket.company.id}`, ticket.company.name) : <span className="text-ink-3">None</span>}
          </Row>,
        ],
        [
          "Application",
          <Row
            key="application"
            editor={
              <Change<string> ticketId={id} what={`the application on ${n}`} initial={ticket.application?.id ?? ""} patch={(v) => ({ applicationId: v || null })}>
                {(v, set, error) => (
                  <RefSelect label="Application" value={v} set={set} list={withCurrent(options.applications, ticket.application)} none="None" error={error} />
                )}
              </Change>
            }
          >
            {ticket.application ? link(`/applications/${ticket.application.id}`, ticket.application.name) : <span className="text-ink-3">None</span>}
          </Row>,
        ],
        [
          "Affected users",
          <Row
            key="affected"
            editor={
              <Change<string>
                ticketId={id}
                what={`how many people ${n} affects`}
                initial={ticket.affectedUsers == null ? "" : String(ticket.affectedUsers)}
                patch={(v) => ({ affectedUsers: v.trim() === "" ? null : Number(v) })}
              >
                {(v, set, error) => (
                  <Field label="Affected users" optional hint="Leave blank if unknown." error={error}>
                    {(p) => <Input {...p} type="number" inputMode="numeric" min={0} value={v} onChange={(e) => set(e.target.value)} autoFocus />}
                  </Field>
                )}
              </Change>
            }
          >
            {ticket.affectedUsers == null ? <span className="text-ink-3">Unknown</span> : ticket.affectedUsers.toLocaleString("en-PH")}
          </Row>,
        ],
        [
          "Incident",
          <Row
            key="incident"
            editor={
              <Change<string> ticketId={id} what={`the incident ${n} belongs to`} initial={ticket.incident?.id ?? ""} patch={(v) => ({ incidentId: v || null })}>
                {(v, set, error) => (
                  <RefSelect
                    label="Linked incident"
                    value={v}
                    set={set}
                    list={withCurrent(options.incidents, ticket.incident)}
                    none="None"
                    error={error}
                    hint="When many users report the same issue, link their tickets to one incident."
                  />
                )}
              </Change>
            }
          >
            {ticket.incident ? link(`/incidents/${ticket.incident.id}`, ticket.incident.name) : <span className="text-ink-3">None</span>}
          </Row>,
        ],
        [
          "Reported by",
          <span key="reporter">
            {ticket.reporter.id ? link(`/users/${ticket.reporter.id}`, ticket.reporter.name ?? ticket.reporter.email ?? "Someone") : ticket.reporter.name ?? ticket.reporter.email}
            {ticket.reporter.name && ticket.reporter.email && <span className="block text-meta text-ink-3">{ticket.reporter.email}</span>}
          </span>,
        ],
        ["Created on", <span key="created" title={when(ticket.createdAt)}>{`${when(ticket.createdAt)} · ${ago(ticket.createdAt)}`}</span>],
        [
          ticket.isOpen ? "Due" : "Closed",
          ticket.isOpen ? (
            ticket.isOverdue ? (
              <span key="due">
                <Flag letter="!">Overdue</Flag>
                <span className="block text-meta text-ink-3">was due {when(ticket.dueAt)}</span>
              </span>
            ) : (
              when(ticket.dueAt)
            )
          ) : (
            when(ticket.closedAt ?? ticket.resolvedAt)
          ),
        ],
      ]}
    />
  );
}
