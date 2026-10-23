import { BadgeCheck, CalendarDays, History, Phone, Users } from "lucide-react";
import { Avatar } from "@/src/modules/console/platform/ui/avatar";
import { Empty, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { getMe, load } from "@/src/modules/console/platform/lib/api";
import { makeFormat } from "@/src/modules/console/platform/lib/format";
import { type Profile } from "@/src/modules/console/platform/actions/account";
import { HEAT_WEEKS, Heatmap, WeekBars, addDays, mondayOf } from "@/src/modules/console/platform/account/activity";
import { ProfileActions } from "@/src/modules/console/platform/account/profile-actions";

export const metadata = { title: "Your profile" };

// Who you are and what you did, on one page: the person at the top (their
// picture, details, Edit profile and Change password), then what they did
// lately, and day by day, from this app's activity log. The CRM has its own,
// with the month against its targets. Platform staff are in no company and
// have no picture here, so the console's own time zone is used.

type Search = Promise<Record<string, string | string[] | undefined>>;
type Account = { role: { name: string; description: string | null }; team: { name: string } | null; memberSince: string };
type Activity = { days: Record<string, number>; recent: { action: string; target: string; at: string }[] };

/** `actions`: the app's words for its activity log ("purchase_order.created" → "Created a purchase order"). */
export default async function ProfilePage({ searchParams, actions = {} }: { searchParams: Search; actions?: Record<string, string> }) {
  const me = await getMe();
  const params = await searchParams;
  const fmt = makeFormat(me.org ?? { currency: "PHP", locale: "en-PH", timezone: "Asia/Manila" });
  const today = fmt.todayKey();
  const week = params.week === "1" ? 1 : 0;
  const heatStart = addDays(mondayOf(today), -7 * (HEAT_WEEKS - 1));
  const [account, profile, activity] = await Promise.all([
    load<Account>("/auth/account").catch(() => null),
    load<Profile>("/auth/profile"),
    load<Activity>(`/auth/activity?from=${heatStart}&to=${addDays(today, 1)}`).catch(() => ({ days: {}, recent: [] }) as Activity),
  ]);
  const joined = account ? new Intl.DateTimeFormat(me.org?.locale ?? "en-PH", { dateStyle: "medium", timeZone: me.org?.timezone ?? "Asia/Manila" }).format(new Date(account.memberSince)) : null;
  const role = account?.role.name ?? me.role?.name ?? null;
  const team = account?.team?.name ?? me.team?.name ?? null;
  const said = (action: string) => actions[action] ?? action.replaceAll(/[._]/g, " ").replace(/^\w/, (c) => c.toUpperCase());

  return (
    <>
      <Sheet className="mb-5 overflow-hidden">
        <div className="h-24 bg-gradient-to-r from-sage-deep via-sage to-mint sm:h-32" aria-hidden />
        <div className="px-5 pb-5 sm:px-6">
          <div className="-mt-10 flex flex-wrap items-end justify-between gap-3">
            <Avatar name={me.user.fullName} id={me.user.id} photoAt={me.user.photoAt} size="xl" className="ring-4 ring-sheet" />
            <ProfileActions profile={profile} today={today} />
          </div>
          <h1 className="mt-3 text-[1.375rem] leading-tight font-semibold text-ink">{me.user.fullName}</h1>
          <p className="text-meta text-ink-3">{me.user.email}</p>
          <p className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-meta text-ink-2">
            {joined && (
              <span className="inline-flex items-center gap-1.5">
                <CalendarDays className="size-3.5 text-ink-3" aria-hidden />
                Joined {joined}
              </span>
            )}
            {role && (
              <span className="inline-flex items-center gap-1.5">
                <BadgeCheck className="size-3.5 text-ink-3" aria-hidden />
                {role}
              </span>
            )}
            {team && (
              <span className="inline-flex items-center gap-1.5">
                <Users className="size-3.5 text-ink-3" aria-hidden />
                {team}
              </span>
            )}
            {profile.phone && (
              <span className="inline-flex items-center gap-1.5">
                <Phone className="size-3.5 text-ink-3" aria-hidden />
                {profile.phone}
              </span>
            )}
            {me.org && <span className="text-ink-3">{me.org.name}</span>}
          </p>
          {account?.role.description && <p className="mt-2 max-w-3xl text-sm text-ink-2">{account.role.description}</p>}
        </div>
      </Sheet>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_21rem]">
        <Sheet className="min-w-0 px-5 pt-4 pb-3">
          <h2 className="flex items-center gap-2 text-heading text-ink">
            <History className="size-4 text-ink-3" aria-hidden />
            Recent activity
          </h2>
          {activity.recent.length === 0 ? (
            <Empty compact icon="inbox" title="No activity yet">
              What you add or change here shows up as you work.
            </Empty>
          ) : (
            <ul className="mt-2 divide-y divide-rule">
              {activity.recent.map((e, i) => (
                <li key={`${e.at}-${i}`} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                  <span className="min-w-0">
                    <span className="font-medium text-ink">{said(e.action)}</span>
                    {e.target && <span className="text-ink-2"> · {e.target}</span>}
                  </span>
                  <span className="shrink-0 text-meta text-ink-3">{fmt.whenLabel(e.at, today)}</span>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
        <aside className="space-y-5" aria-label="Your activity">
          <WeekBars days={activity.days} today={today} week={week} base="/platform/console/account" />
          <Heatmap days={activity.days} today={today} />
        </aside>
      </div>
    </>
  );
}
