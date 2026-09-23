import Link from "next/link";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { ActivityItem, ActivitySummary, Assignable, CompanyRow, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { ActivityList } from "../components/crm/activity-list";
import { Filters, Pager } from "../components/crm/list-controls";
import { LogActivity } from "../components/crm/log-activity";
import { KINDS } from "../components/crm/words";

export const metadata = { title: "Activities" };

const SIZE = 50;
const STATES = [
  { key: "open", label: "To do", empty: "Nothing to do. Meetings and tasks you plan show up here." },
  { key: "overdue", label: "Overdue", empty: "Nothing overdue." },
  { key: "today", label: "Due today", empty: "Nothing due today." },
  { key: "upcoming", label: "Coming up", empty: "Nothing planned after today." },
  { key: "done", label: "Done", empty: "Nothing done yet. Logged calls, emails and notes show up here." },
] as const;
type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function ActivitiesPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "activities.view")) return <NoAccess what="activities" />;
  const params = await searchParams;
  const state = STATES.find((s) => s.key === one(params.state)) ?? STATES[0];
  const [kind, owner] = [one(params.kind), one(params.owner)];
  const page = Math.max(1, Number(one(params.page)) || 1);
  const query = new URLSearchParams({ state: state.key, limit: String(SIZE), offset: String((page - 1) * SIZE) });
  if (kind) query.set("kind", kind);
  if (owner) query.set("owner", owner);
  const [list, counts, people, companies] = await Promise.all([
    load<Paged<ActivityItem>>(`/activities?${query}`),
    load<ActivitySummary>(`/activities/summary?owner=${owner || "all"}`),
    load<Assignable[]>("/people/assignable"),
    can(me, "customers.view") ? load<Paged<CompanyRow>>("/companies?limit=200") : Promise.resolve({ items: [], total: 0 }),
  ]);
  const tab = (key: string) => {
    const q = new URLSearchParams({ ...(key !== "open" && { state: key }), ...(kind && { kind }), ...(owner && { owner }) });
    return `/activities${q.size ? `?${q}` : ""}`;
  };
  const count: Partial<Record<string, number>> = { open: counts.open, overdue: counts.overdue, today: counts.today, upcoming: counts.upcoming };

  return (
    <>
      <PageHeader title="Activities">Calls, meetings, emails, notes and tasks{me.role?.scope === "own" ? " of yours" : me.role?.scope === "team" ? " in your team" : ""}.</PageHeader>

      <nav aria-label="Show" className="mb-4 flex flex-wrap gap-1.5">
        {STATES.map((s) => (
          <Link
            key={s.key}
            href={tab(s.key)}
            aria-current={s.key === state.key ? "page" : undefined}
            className={`rounded-full border px-3 py-1 text-meta ${
              s.key === state.key
                ? "border-hema bg-hema-tint font-semibold text-hema"
                : "border-rule-strong bg-sheet text-ink-2 hover:border-hema hover:text-hema"
            }`}
          >
            {s.label}
            {count[s.key] ? <span className={s.key === "overdue" ? " text-danger" : " text-ink-3"}> {count[s.key]}</span> : null}
          </Link>
        ))}
      </nav>

      <Filters
        selects={[
          { name: "kind", label: "Kind", options: [{ value: "", label: "Every kind" }, ...KINDS.map((k) => ({ value: k.kind, label: `${k.label}s` }))] },
          ...(me.role?.scope !== "own"
            ? [{ name: "owner", label: "Whose", options: [{ value: "", label: "Everyone you can see" }, { value: "me", label: "Mine" }] }]
            : []),
        ]}
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <div>
          <Sheet className="px-5 pt-2 pb-2">
            <ActivityList activities={list.items} org={me.org} empty={state.empty} />
          </Sheet>
          <Pager total={list.total} page={page} size={SIZE} base={tab(state.key)} />
        </div>
        {can(me, "activities.create") && (
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="logActivity">Log or plan</SectionTitle>
            <div className="mt-3">
              <LogActivity org={me.org} now={new Date().toISOString()} people={people} companies={companies.items.map((c) => ({ id: c.id, name: c.name }))} />
            </div>
          </Sheet>
        )}
      </div>
    </>
  );
}
