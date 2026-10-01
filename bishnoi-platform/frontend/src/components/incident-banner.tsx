import Link from "next/link";
import { api } from "@/src/platform/lib/api";
import type { Incident } from "../lib/types";
import { INCIDENT_STATUSES } from "../lib/words";

// On every screen, above everything: the incidents serious enough to say so
// (how serious is Settings > Notifications). Quiet when there are none, and
// when the API can't be asked: the page below says why on its own.

export async function IncidentBanner() {
  const incidents = await api
    .get<{ incidents: Incident[] }>("/platform/banner")
    .then((b) => b.incidents)
    .catch(() => []);
  if (incidents.length === 0) return null;
  return (
    <div role="status" className="mb-5 space-y-1.5">
      {incidents.map((i) => (
        <Link
          key={i.id}
          href={`/incidents/${i.id}`}
          className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[3px] border border-danger/40 bg-danger-tint px-4 py-2.5 text-sm hover:border-danger"
        >
          <span className="inline-flex items-center gap-2 font-semibold text-danger">
            <span aria-hidden className="size-2 animate-pulse rounded-full bg-danger" />
            {i.severity === "critical" ? "Critical incident" : "Incident"} · {INCIDENT_STATUSES[i.status].label}
          </span>
          <span className="min-w-0 flex-1 truncate text-ink">
            {i.number} {i.title}
            {i.application && <span className="text-ink-2"> · {i.application.name}</span>}
          </span>
          <span className="text-meta font-semibold text-danger">Open it</span>
        </Link>
      ))}
    </div>
  );
}
