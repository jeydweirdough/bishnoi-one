import Link from "next/link";
import { Flag } from "@/src/platform/ui/marks";
import { HEALTH, INCIDENT_SEVERITIES, INCIDENT_STATUSES, SEVERITIES, TICKET_KINDS, TICKET_STATUSES } from "../lib/words";
import type { Health, IncidentSeverity, IncidentStatus, Severity, TicketKind, TicketStatus } from "../lib/types";

// How the platform marks things. The word is always there; colour only
// backs it up, so nothing depends on telling red from green.

const DOT: Record<Health, string> = {
  operational: "bg-filed",
  degraded: "bg-due-today",
  down: "bg-danger",
  maintenance: "bg-hema",
  unknown: "bg-control",
  retired: "bg-rule-strong",
};

/** ● Operational: a dot and the word. */
export function HealthMark({ status, label }: { status: Health; label?: string }) {
  const bad = status === "down";
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap text-meta ${bad ? "font-semibold text-danger" : "text-ink-2"}`}>
      <span aria-hidden className={`size-2 shrink-0 rounded-full ${DOT[status]} ${status === "degraded" ? "ring-2 ring-due-today/25" : ""}`} />
      {label ?? HEALTH[status]}
    </span>
  );
}

// Critical is the one that flags; the rest are words in rising ink.
const SEVERITY_STYLE: Record<Severity, string> = {
  critical: "",
  high: "border border-ink bg-ink text-white",
  medium: "border border-ink-2 text-ink-2",
  low: "border border-rule-strong text-ink-3",
};

export function SeverityMark({ severity }: { severity: Severity }) {
  if (severity === "critical") return <Flag letter="!">{SEVERITIES.critical}</Flag>;
  return <span className={`inline-flex h-5 items-center rounded-full px-1.5 text-stamp uppercase ${SEVERITY_STYLE[severity]}`}>{SEVERITIES[severity]}</span>;
}

export function IncidentSeverityMark({ severity }: { severity: IncidentSeverity }) {
  if (severity === "critical") return <Flag letter="!">{INCIDENT_SEVERITIES.critical}</Flag>;
  return (
    <span className={`inline-flex h-5 items-center rounded-full px-1.5 text-stamp uppercase ${severity === "major" ? "border border-ink bg-ink text-white" : "border border-rule-strong text-ink-3"}`}>
      {INCIDENT_SEVERITIES[severity]}
    </span>
  );
}

export function TicketStatusMark({ status }: { status: TicketStatus }) {
  const done = status === "resolved" || status === "closed";
  return (
    <span className={`text-stamp whitespace-nowrap uppercase ${done ? "text-ink-3" : status === "reported" ? "text-ink font-bold" : "text-ink-2"}`}>
      {TICKET_STATUSES[status]}
    </span>
  );
}

export function KindMark({ kind }: { kind: TicketKind }) {
  return <span className="text-meta whitespace-nowrap text-ink-3">{TICKET_KINDS[kind].one}</span>;
}

export function IncidentStatusMark({ status }: { status: IncidentStatus }) {
  return (
    <span className={`text-stamp whitespace-nowrap uppercase ${status === "resolved" ? "text-ink-3" : status === "investigating" ? "text-danger" : "text-ink-2"}`}>
      {INCIDENT_STATUSES[status].label}
    </span>
  );
}

/** Reported → … → Closed, with where the ticket is. */
export function Lifecycle({ status }: { status: TicketStatus }) {
  const steps = Object.keys(TICKET_STATUSES) as TicketStatus[];
  const at = steps.indexOf(status);
  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-1 text-meta" aria-label="Where it is">
      {steps.map((s, i) => (
        <li key={s} className="inline-flex items-center gap-1">
          {i > 0 && <span aria-hidden className={`h-px w-3 ${i <= at ? "bg-hema" : "bg-rule-strong"}`} />}
          <span
            aria-current={i === at ? "step" : undefined}
            className={`rounded-full px-1.5 py-0.5 ${i === at ? "bg-hema font-semibold text-white" : i < at ? "text-hema" : "text-ink-3"}`}
          >
            {TICKET_STATUSES[s]}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** A page's sections as tabs under its header; the choice lives in the URL. */
export function Tabs({ tabs, current }: { tabs: { href: string; label: string; key: string; count?: number }[]; current: string }) {
  return (
    <nav aria-label="Sections" className="mb-5 flex gap-5 overflow-x-auto border-b border-rule">
      {tabs.map((t) => (
        <Link
          key={t.key}
          href={t.href}
          scroll={false}
          aria-current={t.key === current ? "page" : undefined}
          className={`-mb-px shrink-0 border-b-2 pb-2 text-sm ${t.key === current ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"}`}
        >
          {t.label}
          {t.count ? <span className="ml-1 text-meta font-normal text-ink-3">{t.count}</span> : null}
        </Link>
      ))}
    </nav>
  );
}

/** A small number beside a label, for a list's headings. */
export function Count({ n }: { n: number }) {
  return <span className="ml-1.5 text-meta font-normal text-ink-3">{n.toLocaleString("en-PH")}</span>;
}
