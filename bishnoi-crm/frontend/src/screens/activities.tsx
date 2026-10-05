import { SelectAllBox, SelectToggle, SelectionProvider } from "@/src/platform/bulk/selection";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { buttonClass } from "@/src/platform/ui/button";
import type { ActivityItem, ActivitySummary, Assignable, Bucket, CompanyRow, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { ActivityCalendar, monthRange } from "../components/crm/activity-calendar";
import { NewCallButton } from "../components/crm/new-call";
import { ActivityList } from "../components/crm/activity-list";
import { dayOf, followUpRow } from "../components/crm/follow-up-rows";
import { Filters, Pager } from "../components/crm/list-controls";
import { LogActivityButton } from "../components/crm/log-activity-button";
import { KINDS } from "../components/crm/words";
import { shiftMonth } from "../components/field/words";
import { FollowUpItem } from "../components/follow-up-item";
import { FollowUpsBulk } from "../components/follow-ups-bulk";

export const metadata = { title: "Activities" };

// One place for everything done with customers:
// - To do: the meetings and tasks still ahead, grouped by when they're due,
//   ticked off here (one at a time, or many at once);
// - History: every call, meeting, email, note and task that's been done;
// - Calendar: a month of them, a day to a box, done and still to do.
const SIZE = 50;
const GROUPS: { bucket: Bucket; label: string }[] = [
  { bucket: "overdue", label: "Overdue" },
  { bucket: "today", label: "Today" },
  { bucket: "upcoming", label: "Coming up" },
];

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function ActivitiesPage({ searchParams, calendar = false }: { searchParams: Search; calendar?: boolean }) {
  const me = await getCompanyMe();
  if (!can(me, "activities.view")) return <NoAccess what="activities" />;
  const params = await searchParams;
  // The calendar has its own place in the menu (/calendar); the old address still opens it.
  const view = calendar ? "calendar" : ((["history", "calendar"] as const).find((v) => v === one(params.view)) ?? "todo");
  const teamWide = me.role?.scope !== "own";
  // A lead manages people: their team first. A salesperson has only their own.
  const who = teamWide && one(params.who) !== "me" ? "team" : "me";
  const person = who === "team" ? one(params.person) : "";
  const kind = one(params.kind);
  const page = Math.max(1, Number(one(params.page)) || 1);
  const href = (v: string, w = who) => {
    const q = new URLSearchParams({ ...(v !== "todo" && { view: v }), ...(w === "me" && teamWide && { who: w }), ...(w === "team" && person && { person }) });
    if (v === "calendar") q.delete("view");
    return `${v === "calendar" ? "/calendar" : "/activities"}${q.size ? `?${q}` : ""}`;
  };

  const today = dayOf(new Date().toISOString(), me.org.timezone);
  const month = /^\d{4}-\d{2}$/.test(one(params.month)) ? one(params.month) : today.slice(0, 7);
  const query =
    view === "todo"
      ? new URLSearchParams({ state: "open", limit: "200" })
      : view === "calendar"
        ? new URLSearchParams({ ...monthRange(month), limit: "500" })
        : new URLSearchParams({ state: "done", limit: String(SIZE), offset: String((page - 1) * SIZE), ...(kind && { kind }) });
  if (who === "me") query.set("owner", "me");
  else if (person) query.set("owner", person);
  const [list, counts, people, companies] = await Promise.all([
    load<Paged<ActivityItem>>(`/activities?${query}`),
    load<ActivitySummary>(`/activities/summary?owner=${who === "me" ? "me" : "all"}`),
    load<Assignable[]>("/people/assignable"),
    can(me, "customers.view") ? load<Paged<CompanyRow>>("/companies?limit=200") : Promise.resolve({ items: [], total: 0 }),
  ]);
  const monthHref = (m: string) => `${href("calendar")}${href("calendar").includes("?") ? "&" : "?"}month=${m}`;
  const monthName = new Intl.DateTimeFormat("en-PH", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${month}-01T00:00:00Z`));
  const rows = view === "todo" ? list.items.map((a) => followUpRow(a, today, me.org.timezone, { place: who === "team" && !person ? a.owner.name : undefined })) : [];
  const personName = person ? people.find((p) => p.id === person)?.name : undefined;
  const editable = rows.filter((f) => f.canEdit).map((f) => ({ id: f.id, name: f.title }));

  return (
    <SelectionProvider key={`${view}-${who}`} items={editable} toggled>
      <PageHeader
        title={view === "calendar" ? "Calendar" : "Activities"}
        actions={
          can(me, "activities.create") && (
            <>
              {view === "calendar" && <NewCallButton />}
              <LogActivityButton
                variant={view === "calendar" ? "default" : "primary"}
                org={me.org}
                now={new Date().toISOString()}
                people={people}
                companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
              />
            </>
          )
        }
      >
        {view === "calendar" ? "Your calls and visits by day. Plan one with New call; tick it off afterwards to say how it went." : "Calls, meetings, emails, notes and tasks. What's still to do comes first."}
      </PageHeader>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <ToggleLinks
          current={view}
          options={[
            { value: "todo", label: `To do${counts.open ? ` · ${counts.open}` : ""}`, href: href("todo") },
            { value: "history", label: "History", href: href("history") },
            { value: "calendar", label: "Calendar", href: href("calendar") },
          ]}
        />
        {teamWide && (
          <ToggleLinks
            current={who}
            options={[
              { value: "me", label: "Mine", href: href(view, "me") },
              { value: "team", label: me.role?.scope === "all" ? "Everyone" : me.role?.scope === "managed" ? "My teams" : "My team", href: href(view, "team") },
            ]}
          />
        )}
        {personName && (
          <span className="inline-flex items-center gap-2 rounded-[6px] border border-hema bg-hema-tint px-2.5 py-1 text-meta text-ink">
            {personName}&apos;s only
            <a href={href(view, "team").replace(/[?&]person=[^&]*/, "")} className="font-semibold hover:underline" aria-label="Show the whole team">
              ✕
            </a>
          </span>
        )}
        {view === "todo" && counts.overdue > 0 && !person && <span className="text-meta font-semibold text-danger">{counts.overdue} overdue</span>}
        {view === "todo" && editable.length > 1 && (
          <span className="ml-auto">
            <SelectToggle />
          </span>
        )}
      </div>

      {view === "history" && (
        <Filters selects={[{ name: "kind", label: "Kind", options: [{ value: "", label: "Every kind" }, ...KINDS.map((k) => ({ value: k.kind, label: `${k.label}s` }))] }]} />
      )}

      {view === "calendar" ? (
        <Sheet className="px-5 pt-3 pb-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="text-heading text-ink">{monthName}</h2>
            <span className="ml-auto flex gap-1">
              <a href={monthHref(shiftMonth(month, -1))} className={buttonClass("quiet", "sm")} aria-label="The month before">
                ‹ Before
              </a>
              {month !== today.slice(0, 7) && (
                <a href={monthHref(today.slice(0, 7))} className={buttonClass("quiet", "sm")}>
                  This month
                </a>
              )}
              <a href={monthHref(shiftMonth(month, 1))} className={buttonClass("quiet", "sm")} aria-label="The month after">
                After ›
              </a>
            </span>
          </div>
          {list.total > list.items.length && (
            <p className="mb-2 text-meta text-ink-3">
              Showing the first {list.items.length} of {list.total}. Pick one person to see all of theirs.
            </p>
          )}
          <ActivityCalendar items={list.items} month={month} today={today} timeZone={me.org.timezone} showOwner={who === "team" && !person} />
        </Sheet>
      ) : view === "todo" ? (
        <Sheet className="px-5 pt-2 pb-2">
          <div className="border-b border-rule empty:hidden">
            <SelectAllBox>
              <span className="text-meta font-semibold text-ink-2">Select all {editable.length}</span>
            </SelectAllBox>
          </div>
          {rows.length === 0 ? (
            <Empty icon="followUps" title="Nothing to do" actions={can(me, "activities.create") && <LogActivityButton
                    label="Plan a meeting or task"
                    org={me.org}
                    now={new Date().toISOString()}
                    people={people}
                    companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
                  />}>
              Meetings and tasks you plan show up here, from Log activity or from a customer&apos;s page.
            </Empty>
          ) : (
            GROUPS.map(({ bucket, label }) => {
              const group = rows.filter((f) => f.bucket === bucket);
              if (!group.length) return null;
              return (
                <section key={bucket} className="mt-2" aria-label={label}>
                  <h2 className={`border-b border-rule pb-1 text-meta font-semibold ${bucket === "overdue" ? "text-danger" : "text-ink-2"}`}>
                    {label} <span className="font-normal text-ink-3">· {group.length}</span>
                  </h2>
                  <ul className="divide-y divide-rule">
                    {group.map((f) => (
                      <FollowUpItem key={f.id} row={f} today={today} org={me.org} />
                    ))}
                  </ul>
                </section>
              );
            })
          )}
        </Sheet>
      ) : (
        <>
          <Sheet className="px-5 pt-2 pb-2">
            <ActivityList activities={list.items} org={me.org} empty="Nothing logged yet. Calls, emails, notes, and tasks once done, show up here." />
          </Sheet>
          <Pager total={list.total} page={page} size={SIZE} base={`${href("history")}${kind ? `${href("history").includes("?") ? "&" : "?"}kind=${kind}` : ""}`} />
        </>
      )}
      {view === "todo" && <FollowUpsBulk people={people} state="open" org={me.org} />}
    </SelectionProvider>
  );
}
