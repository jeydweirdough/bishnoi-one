import { Plus } from "lucide-react";
import Link from "next/link";
import { FollowUpItem } from "../components/follow-up-item";
import { LinkButton } from "@/src/platform/ui/button";
import { Figure } from "@/src/platform/ui/figure";
import { Icon, listIcon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { listName } from "@/src/platform/lib/labels";
import { salesWorkspace, teamsFor } from "@/src/platform/lib/module";
import { orgFormat } from "@/src/platform/lib/org";
import type { Summary } from "@/src/platform/lib/types";

export const metadata = { title: "Overview" };

export default async function Overview() {
  const [ws, me, fmt] = await Promise.all([salesWorkspace(), getCompanyMe(), orgFormat()]);
  // Everything they sell, counted once. Not one division at a time.
  const summary = await load<Summary>("/sales/summary");
  const { counts } = summary;
  const { activity_kind: kinds, outcome: outcomes } = me.lists;
  const canAdd = teamsFor(ws, "create").length > 0;

  return (
    <>
      <PageHeader
        title="Overview"
        actions={
          canAdd && (
            <LinkButton href="/customers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add customer
            </LinkButton>
          )
        }
      >
        {ws.teams.length === 1 ? "Your team: " : "Your teams: "}
        {ws.teams.map((t) => (ws.manyDivisions ? `${t.divisionName} · ${t.name}` : t.name)).join(", ")}
      </PageHeader>

      <Sheet className="mb-5 grid grid-cols-2 divide-rule sm:grid-cols-5 sm:divide-x [&>*:nth-child(n+3)]:border-t [&>*:nth-child(n+3)]:border-rule sm:[&>*:nth-child(n+3)]:border-t-0">
        <Figure label="Customers" value={counts.customers} href="/customers" />
        <Figure label="Leads" value={counts.leads} href="/customers?status=lead" />
        <Figure label="Overdue for you" value={counts.overdue} flag href="/follow-ups" />
        <Figure label="Due today for you" value={counts.dueToday} href="/follow-ups" />
        <Figure label="Coming up for you" value={counts.upcoming} href="/follow-ups" />
      </Sheet>

      <div className="grid gap-5 lg:grid-cols-2">
        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle
            icon="followUps"
            action={
              <Link href="/follow-ups" className="text-meta font-medium text-hema hover:underline">
                All follow-ups
              </Link>
            }
          >
            Due for you
          </SectionTitle>
          {summary.dueFollowUps.length === 0 ? (
            <Empty icon="followUps" title="Nothing due today">Overdue and today&apos;s follow-ups show up here.</Empty>
          ) : (
            <ul className="divide-y divide-rule">
              {summary.dueFollowUps.map((f) => (
                <FollowUpItem
                  key={f.id}
                  today={summary.today}
                  row={{
                    ...f,
                    place: ws.manyDivisions ? `${f.divisionName} · ${f.teamName}` : f.teamName,
                    canEdit: f.can.edit,
                  }}
                  org={me.org}
                />
              ))}
            </ul>
          )}
        </Sheet>

        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle icon="activity">Recent activity</SectionTitle>
          {summary.recentActivity.length === 0 ? (
            <Empty icon="activity" title="No activity yet">Whatever your team logs against a customer shows up here.</Empty>
          ) : (
            <ul className="divide-y divide-rule">
              {summary.recentActivity.map((a) => (
                <li key={a.id} className="py-3">
                  <p className="text-meta text-ink-3">
                    <span className="inline-flex items-center gap-1 align-[-2px] font-semibold text-ink-2">
                      <Icon name={listIcon(kinds.find((k) => k.code === a.kind) ?? { code: a.kind, icon: null })} className="size-3.5" />
                      {listName(kinds, a.kind)}
                    </span>
                    {a.outcome && ` · ${listName(outcomes, a.outcome)}`} · {fmt.whenLabel(a.occurredAt, summary.today)} · {a.by.name}
                  </p>
                  <p className="mt-0.5">
                    <Link href={`/customers/${a.customerId}`} className="font-medium text-hema hover:underline">
                      {a.customerName}
                    </Link>
                    <span className="text-ink-2"> — {a.summary}</span>
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
      </div>
    </>
  );
}
