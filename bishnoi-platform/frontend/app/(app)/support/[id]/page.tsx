// One ticket: what was reported, where it is, who has it, and everything
// said and done about it since.
import { Flag } from "@/src/platform/ui/marks";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { KindMark, Lifecycle, SeverityMark, TicketStatusMark } from "@/src/components/marks";
import { TicketFields } from "@/src/components/support/ticket-fields";
import { DeleteRecord } from "@/src/components/delete-record";
import { getStaff } from "@/src/components/gate";
import { AddNote, EditTicketWords } from "@/src/components/support/ticket-forms";
import type { Options, TicketDetail, TicketNote } from "@/src/lib/types";
import { TICKET_KINDS, TICKET_STATUSES, ago, when } from "@/src/lib/words";

type Params = Promise<{ id: string }>;

const getTicket = (id: string) => load<{ ticket: TicketDetail }>(`/platform/tickets/${enc(id)}`).then((b) => b.ticket);

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    const t = await getTicket(id);
    return { title: `${t.number} ${t.title}` };
  } catch {
    return { title: "Ticket" };
  }
}

/** "Ana moved it Assigned → Investigating", with what they said. */
function Note({ note }: { note: TicketNote }) {
  const moved = note.to && note.from !== note.to;
  return (
    <li className="py-3">
      <p className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <span className="text-sm">
          <b className="font-semibold text-ink">{note.author}</b>{" "}
          {moved ? (
            note.from ? (
              <span className="text-ink-2">
                moved it <TicketStatusMark status={note.from} /> → <TicketStatusMark status={note.to!} />
              </span>
            ) : (
              <span className="text-ink-2">
                logged it as <TicketStatusMark status={note.to!} />
              </span>
            )
          ) : (
            <span className="text-ink-2">added a note</span>
          )}
        </span>
        <time dateTime={note.createdAt} title={when(note.createdAt)} className="text-meta text-ink-3">
          {ago(note.createdAt)}
        </time>
      </p>
      {note.body && <p className="mt-1 text-sm whitespace-pre-line text-ink">{note.body}</p>}
    </li>
  );
}

export default async function TicketPage({ params }: { params: Params }) {
  const { id } = await params;
  const [ticket, options, staff] = await Promise.all([getTicket(id), load<Options>("/platform/options"), getStaff()]);
  const newestFirst = [...ticket.notes].reverse();

  return (
    <>
      <PageHeader
        crumbs={[{ href: `/support?kind=${ticket.kind}`, label: `Support · ${TICKET_KINDS[ticket.kind].many}` }]}
        title={`${ticket.number} ${ticket.title}`}
        // Its title and description are the ticket's own words, so their editor sits with the title.
        tools={
          <>
            <EditTicketWords ticket={ticket} />
            {staff.canAdminister && (
              <DeleteRecord
                kind="ticket"
                id={ticket.id}
                name={`${ticket.number} ${ticket.title}`}
                after="/support"
                done="Ticket deleted"
                body="It goes with its notes: for a ticket raised by mistake, or a test. It can't be undone; to keep it, close it instead."
              />
            )}
          </>
        }
      >
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <KindMark kind={ticket.kind} />
          <SeverityMark severity={ticket.severity} />
          <TicketStatusMark status={ticket.status} />
          {ticket.isOverdue && <Flag letter="!">Overdue</Flag>}
          <span className="text-meta">
            Reported by {ticket.reporter.name ?? ticket.reporter.email ?? "someone"}
            {ticket.company && ` at ${ticket.company.name}`} · {ago(ticket.createdAt)}
          </span>
        </span>
      </PageHeader>

      <Sheet className="mb-5 px-5 py-4">
        <Lifecycle status={ticket.status} />
        <p className="mt-2 text-meta text-ink-3">
          {ticket.isOpen
            ? `${TICKET_STATUSES[ticket.status]} now. Change the status beside it under Details; steps can be skipped.`
            : `${TICKET_STATUSES[ticket.status]} ${ago(ticket.closedAt ?? ticket.resolvedAt)}. Moving it back to an earlier step reopens it.`}
        </p>
      </Sheet>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <div className="space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="message">What they said</SectionTitle>
            {ticket.description ? (
              <p className="mt-2 text-sm whitespace-pre-line text-ink">{ticket.description}</p>
            ) : (
              <p className="mt-2 text-meta text-ink-3">No description. Add one with the pencil beside the title.</p>
            )}
          </Sheet>

          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="history">Notes and moves</SectionTitle>
            {newestFirst.length === 0 ? (
              <p className="py-2 text-meta text-ink-3">Nothing yet. Add a note below as you work it.</p>
            ) : (
              <ol className="mt-1 divide-y divide-rule">
                {newestFirst.map((n) => (
                  <Note key={n.id} note={n} />
                ))}
              </ol>
            )}
            <div className="mt-2">
              <AddNote ticketId={ticket.id} />
            </div>
          </Sheet>
        </div>

        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="particulars">Details</SectionTitle>
          <div className="mt-3">
            <TicketFields ticket={ticket} options={options} />
          </div>
        </Sheet>
      </div>
    </>
  );
}
