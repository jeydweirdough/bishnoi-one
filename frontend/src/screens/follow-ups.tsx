import Link from "next/link";
import { FollowUpsBulk } from "../components/follow-ups-bulk";
import { SelectAllBox, SelectToggle, SelectionProvider } from "@/src/platform/bulk/selection";
import { FollowUpItem } from "../components/follow-up-item";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { ActivityItem, Assignable, Bucket, Paged } from "@/src/platform/lib/types";
import { dayOf, followUpRow } from "../components/crm/follow-up-rows";

export const metadata = { title: "Follow-ups" };

const GROUPS: { bucket: Bucket; label: string }[] = [
  { bucket: "overdue", label: "Overdue" },
  { bucket: "today", label: "Today" },
  { bucket: "upcoming", label: "Coming up" },
];

function Toggle({ options, current }: { options: { href: string; label: string; value: string }[]; current: string }) {
  return (
    <div className="inline-flex rounded-[3px] border border-rule-strong bg-sheet p-0.5">
      {options.map((o) => (
        <Link
          key={o.value}
          href={o.href}
          aria-current={o.value === current ? "true" : undefined}
          className={`rounded-[2px] px-3 py-1 text-meta ${
            o.value === current ? "bg-hema-tint font-semibold text-hema" : "text-ink-2 hover:text-ink"
          }`}
        >
          {o.label}
        </Link>
      ))}
    </div>
  );
}

export default async function FollowUpsPage({ searchParams }: { params: Promise<Record<string, never>>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const search = await searchParams;
  const me = await getCompanyMe();
  const who = search.who === "team" ? "team" : "me";
  const state = search.state === "done" ? "done" : "open";
  const teamWide = me.role?.scope !== "own";

  // Follow-ups are tasks: the person's own, or everyone's within their reach.
  const query = new URLSearchParams({ kind: "task", state, limit: state === "done" ? "50" : "200" });
  if (who === "me") query.set("owner", "me");
  const [list, people] = await Promise.all([load<Paged<ActivityItem>>(`/activities?${query}`), load<Assignable[]>("/people/assignable")]);
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  const items = list.items.map((a) =>
    followUpRow(a, today, me.org.timezone, {
      // Whose it is, on the team list.
      place: who === "team" ? a.owner.name : undefined,
    }),
  );
  const href = (w: string, s: string) => `/follow-ups?who=${w}&state=${s}`;

  const editable = items.filter((f) => f.canEdit).map((f) => ({ id: f.id, name: f.title }));

  return (
    <SelectionProvider key={`${who}-${state}`} items={editable} toggled>
      <PageHeader title="Follow-ups" />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {teamWide && (
          <Toggle
            current={who}
            options={[
              { value: "me", label: "Mine", href: href("me", state) },
              { value: "team", label: me.role?.scope === "all" ? "Everyone" : "Whole team", href: href("team", state) },
            ]}
          />
        )}
        <Toggle
          current={state}
          options={[
            { value: "open", label: "To do", href: href(who, "open") },
            { value: "done", label: "Done", href: href(who, "done") },
          ]}
        />
        {editable.length > 1 && (
          <span className="ml-auto">
            <SelectToggle />
          </span>
        )}
      </div>

      <Sheet className="px-5 pt-2 pb-2">
        <div className="border-b border-rule empty:hidden">
          <SelectAllBox>
            <span className="text-meta font-semibold text-ink-2">Select all {editable.length}</span>
          </SelectAllBox>
        </div>
        {items.length === 0 ? (
          <Empty icon="followUps" title={state === "open" ? "Nothing to do" : "Nothing done yet"}>
            {state === "open"
              ? "Follow-ups are the tasks you plan: from a company's or contact's page, from Activities, or for many customers at once."
              : "Finished follow-ups from the last while show up here."}
          </Empty>
        ) : state === "done" ? (
          <ul className="divide-y divide-rule">
            {items.map((f) => (
              <FollowUpItem key={f.id} row={f} today={today} org={me.org} />
            ))}
          </ul>
        ) : (
          GROUPS.map(({ bucket, label }) => {
            const rows = items.filter((f) => f.bucket === bucket);
            if (!rows.length) return null;
            return (
              <section key={bucket} className="mt-2" aria-label={label}>
                <h2 className="border-b border-rule pb-1 text-meta font-semibold text-ink-2">
                  {label} <span className="font-normal text-ink-3">· {rows.length}</span>
                </h2>
                <ul className="divide-y divide-rule">
                  {rows.map((f) => (
                    <FollowUpItem key={f.id} row={f} today={today} org={me.org} />
                  ))}
                </ul>
              </section>
            );
          })
        )}
      </Sheet>
      <FollowUpsBulk people={people} state={state} org={me.org} />
    </SelectionProvider>
  );
}
