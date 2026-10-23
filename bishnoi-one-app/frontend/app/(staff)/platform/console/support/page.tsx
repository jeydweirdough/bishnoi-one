// Support: every complaint, bug report, system issue, feature request and
// support ticket, one list with a kind each.
import Link from "next/link";
import { X } from "lucide-react";
import { Flag } from "@/src/modules/console/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { load } from "@/src/modules/console/platform/lib/api";
import { KindMark, SeverityMark, Tabs, TicketStatusMark } from "@/src/modules/console/components/marks";
import { Filters } from "@/src/modules/console/components/support/filters";
import { LogTicket } from "@/src/modules/console/components/support/ticket-forms";
import type { Options, Severity, Ticket, TicketKind } from "@/src/modules/console/lib/types";
import { SEVERITIES, TICKET_KINDS, ago, when } from "@/src/modules/console/lib/words";

export const metadata = { title: "Support" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const KINDS = Object.keys(TICKET_KINDS) as TicketKind[];

export default async function SupportPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const kind = (KINDS as string[]).includes(one(params.kind)) ? (one(params.kind) as TicketKind) : null;
  const state = ["done", "all"].includes(one(params.state)) ? one(params.state) : "open";
  const severity = one(params.severity) in SEVERITIES ? (one(params.severity) as Severity) : "";
  // The page's own words for its filters; the API's are snake_case.
  const assignee = one(params.assignee) || one(params.assignee_id);
  const applicationId = one(params.application) || one(params.application_id);
  const companyId = one(params.company) || one(params.company_id);
  const q = one(params.q).trim();

  const query = new URLSearchParams({ state });
  if (kind) query.set("kind", kind);
  if (severity) query.set("severity", severity);
  if (assignee) query.set("assignee_id", assignee);
  if (applicationId) query.set("application_id", applicationId);
  if (companyId) query.set("company_id", companyId);
  if (q) query.set("q", q);

  const [list, options] = await Promise.all([
    load<{ tickets: Ticket[]; openByKind: Partial<Record<TicketKind, number>> }>(`/platform/tickets?${query}`),
    load<Options>("/platform/options"),
  ]);

  // Switching kind keeps the other filters.
  const keep = new URLSearchParams(Object.entries(params).flatMap(([k, v]) => (typeof v === "string" && v && k !== "kind" ? [[k, v]] : [])));
  const kindHref = (k: string) => {
    const next = new URLSearchParams(keep);
    if (k) next.set("kind", k);
    return `/platform/console/support${next.size ? `?${next}` : ""}`;
  };
  const without = (...names: string[]) => {
    const next = new URLSearchParams(Object.entries(params).flatMap(([k, v]) => (typeof v === "string" && v && !names.includes(k) ? [[k, v]] : [])));
    return `/platform/console/support${next.size ? `?${next}` : ""}`;
  };
  const openTotal = Object.values(list.openByKind).reduce((n, c) => n + (c ?? 0), 0);
  const appName = options.applications.find((a) => a.id === applicationId)?.name;
  const companyName = options.companies.find((c) => c.id === companyId)?.name;
  const filtered = Boolean(severity || assignee || q || applicationId || companyId || state !== "open");

  return (
    <>
      <PageHeader title="Support" actions={<LogTicket options={options} />}>
        What people have reported, and where each one is. A ticket is one person&apos;s report; when many report the same breakage, link them to an incident.
      </PageHeader>

      <Tabs
        current={kind ?? "all"}
        tabs={[
          { key: "all", label: "All", href: kindHref(""), count: openTotal },
          ...KINDS.map((k) => ({ key: k, label: TICKET_KINDS[k].many, href: kindHref(k), count: list.openByKind[k] ?? 0 })),
        ]}
      />
      <p className="-mt-2 mb-4 text-meta text-ink-3">
        {kind ? TICKET_KINDS[kind].what : "All ticket types. Tab counts show open tickets."}
      </p>

      <Filters
        search="Number, title or reporter"
        selects={[
          {
            name: "state",
            label: "Status",
            options: [
              { value: "", label: "Open" },
              { value: "done", label: "Closed" },
              { value: "all", label: "All" },
            ],
          },
          {
            name: "severity",
            label: "Severity",
            options: [{ value: "", label: "All severities" }, ...(Object.keys(SEVERITIES) as Severity[]).map((s) => ({ value: s, label: SEVERITIES[s] }))],
          },
          {
            name: "assignee",
            label: "Assigned to",
            options: [{ value: "", label: "Anyone" }, { value: "none", label: "Unassigned" }, ...options.staff.map((s) => ({ value: s.id, label: s.name }))],
          },
        ]}
      />

      {(appName || companyName) && (
        <p className="mb-3 flex flex-wrap gap-2 text-meta">
          {appName && (
            <Link href={without("application", "application_id")} className="inline-flex items-center gap-1 rounded-full border border-hema bg-hema-tint px-3 py-1 text-hema" aria-label={`Clear filter: ${appName}`}>
              Only {appName} <X className="size-3.5" aria-hidden />
            </Link>
          )}
          {companyName && (
            <Link href={without("company", "company_id")} className="inline-flex items-center gap-1 rounded-full border border-hema bg-hema-tint px-3 py-1 text-hema" aria-label={`Clear filter: ${companyName}`}>
              Only {companyName} <X className="size-3.5" aria-hidden />
            </Link>
          )}
        </p>
      )}

      <Sheet className="overflow-hidden">
        {list.tickets.length === 0 ? (
          <Empty icon="support" title={filtered ? "No matching tickets." : kind ? `No open ${TICKET_KINDS[kind].many.toLowerCase()}.` : "No open tickets."}>
            {filtered ? "Try another status or fewer filters." : "When an issue is reported, use Log ticket to track it until it is closed."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {list.tickets.map((t) => (
              <li key={t.id} className="px-5 py-3.5">
                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
                  <p className="min-w-0">
                    <Link href={`/platform/console/support/${t.id}`} className="font-semibold text-hema hover:underline">
                      {t.number}
                    </Link>{" "}
                    <span className="text-ink">{t.title}</span>
                  </p>
                  <span className="flex shrink-0 flex-wrap items-center gap-3">
                    {t.isOverdue && <Flag letter="!">Overdue</Flag>}
                    <SeverityMark severity={t.severity} />
                    <TicketStatusMark status={t.status} />
                  </span>
                </div>
                <p className="mt-1 flex flex-wrap items-baseline gap-x-2 text-meta text-ink-2">
                  <KindMark kind={t.kind} />
                  {[t.company?.name, t.application?.name].filter(Boolean).map((x) => (
                    <span key={x}>· {x}</span>
                  ))}
                </p>
                <p className="mt-0.5 text-meta text-ink-3">
                  From {t.reporter.name ?? t.reporter.email ?? "someone"} · {t.assignee ? `with ${t.assignee.name}` : "nobody has it yet"} ·{" "}
                  <time dateTime={t.createdAt} title={when(t.createdAt)}>
                    {ago(t.createdAt)}
                  </time>
                </p>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      {list.tickets.length >= 300 && <p className="mt-3 text-meta text-ink-3">Showing the newest 300. Use the filters to see older tickets.</p>}
    </>
  );
}
