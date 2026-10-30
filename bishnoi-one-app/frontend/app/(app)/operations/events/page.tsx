// Business events (feature plan step 7): what the apps tell each other through the Platform, and
// the deliveries that are stuck, for an operator to retry or skip.
import Link from "next/link";
import type { EventsView } from "@/src/modules/console/actions/events";
import { CheckNow, DeliveryTools } from "@/src/modules/console/components/events/event-tools";
import { ago, when } from "@/src/modules/console/lib/words";
import { load } from "@/src/modules/console/platform/lib/api";
import { getAccount } from "@/src/platform/lib/account";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";

export const metadata = { title: "Events" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const STATES = [
  { key: "stuck", label: "Stuck" },
  { key: "pending", label: "Waiting" },
  { key: "delivered", label: "Delivered" },
  { key: "skipped", label: "Skipped" },
] as const;

export default async function EventsPage({ searchParams }: { searchParams: Search }) {
  const s = await searchParams;
  const state = STATES.find((x) => x.key === s.state)?.key ?? "stuck";
  const [view, me] = await Promise.all([load<EventsView>(`/platform/events?state=${state}`), getAccount()]);
  const canAct = me.staff === "admin";
  return (
    <>
      <PageHeader title="Events" actions={canAct && <CheckNow />}>
        What the apps tell each other through Bishnoi One, delivered in order and retried. A delivery that keeps failing stops here, holding back the ones
        behind it for that app, until you retry or skip it. The check also runs every night.
      </PageHeader>
      <nav className="mb-4 flex flex-wrap gap-2" aria-label="Deliveries by state">
        {STATES.map((x) => (
          <Link
            key={x.key}
            href={`/operations/events?state=${x.key}`}
            aria-current={state === x.key ? "page" : undefined}
            className={`rounded-lg border px-3 py-1.5 text-sm ${state === x.key ? "border-hema bg-hema-tint font-semibold text-ink" : "border-rule-strong bg-sheet text-ink-2 hover:border-hema"}`}
          >
            {x.label} <span className={`tabular-nums ${x.key === "stuck" && view.counts.stuck > 0 ? "font-semibold text-danger" : ""}`}>{view.counts[x.key]}</span>
          </Link>
        ))}
      </nav>
      <Sheet className="px-5 pt-4 pb-2">
        {view.deliveries.length === 0 ? (
          <Empty icon="activity" title={state === "stuck" ? "Nothing stuck" : "Nothing here"}>
            {state === "stuck" ? "Every event reached the apps that take it." : "Deliveries in this state are listed here."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {view.deliveries.map((d) => (
              <li key={`${d.eventId}-${d.target}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-ink">
                    {d.says}{" "}
                    <span className="font-normal text-ink-3">
                      · {d.source} → {d.target}
                    </span>
                  </span>
                  <span className="block truncate text-meta text-ink-3">
                    {d.company ?? "—"} ·{" "}
                    <time dateTime={d.occurredAt} title={when(d.occurredAt)}>
                      {ago(d.occurredAt)}
                    </time>
                    {d.attempts ? ` · ${d.attempts} ${d.attempts === 1 ? "try" : "tries"}` : ""}
                    {d.lastError ? ` · ${d.lastError}` : ""}
                  </span>
                </span>
                {canAct && (d.status === "stuck" || d.status === "pending") && <DeliveryTools eventId={d.eventId} target={d.target} />}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      <Sheet className="mt-4 px-5 py-4">
        <SectionTitle icon="activity">The events Bishnoi One knows</SectionTitle>
        <ul className="mt-2 divide-y divide-rule text-sm">
          {view.kinds.map((k) => (
            <li key={k.kind} className="flex flex-wrap gap-x-3 py-2">
              <span className="w-48 font-mono text-meta text-ink-2">{k.kind}</span>
              <span className="min-w-0 flex-1 text-ink">{k.says}</span>
              <span className="text-meta text-ink-3">
                {k.source} → {k.takers.join(", ")}
              </span>
            </li>
          ))}
        </ul>
      </Sheet>
    </>
  );
}
