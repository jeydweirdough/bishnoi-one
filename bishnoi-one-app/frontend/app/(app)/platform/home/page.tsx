import Link from "next/link";
import { redirect } from "next/navigation";
import { Download } from "lucide-react";
import { getAccount } from "@/src/platform/lib/account";
import { ago } from "@/src/modules/console/lib/words";
import { ReportChartView } from "@/src/platform/reports/chart";
import { buttonClass } from "@/src/platform/ui/button";
import { Donut } from "@/src/platform/ui/donut";
import { Pill, TrendCard } from "@/src/platform/ui/figures";
import { Icon } from "@/src/platform/ui/icons";
import { Later } from "@/src/platform/ui/later";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { Bone, ListRows } from "@/src/platform/ui/skeleton";
import { EMPTY_OVERVIEW, loadOverview, type Overview } from "@/src/one/home/overview";
import { PeriodSelect } from "@/src/one/home/period-select";
import { PERIODS, periodOf } from "@/src/one/home/periods";

export const metadata = { title: "Home" };

// The Admin Console's Home (2026-10-30; laid out as a dashboard 2026-10-31): user control at a glance, for
// the company's administrators: who's here, who signs in, how safe the sign-ins are, what waits on them, and
// who can open which app. Counted by the Platform alone (/identity/company/overview), so it's quick. No
// money here: the Admin Console is people. The page is drawn at once; the figures stream in.

type Search = Promise<Record<string, string | string[] | undefined>>;

const PEOPLE = "/platform/roles/people";
// The chart's three series, in a fixed order (checked for colour-blind separation and contrast on white).
const SERIES = ["#2a78d6", "#eb6834", "#199e70"];
const STATUS = { active: "#2a78d6", off: "#eb6834", bin: "#a3a29b" };
const TINTS = {
  blue: { bg: "#e8f1fc", ink: "#2a78d6" },
  green: { bg: "#e3f4ec", ink: "#167a57" },
  orange: { bg: "#fdeee7", ink: "#c4532a" },
  violet: { bg: "#eeebfb", ink: "#6250d6" },
};
const n = (v: number, one: string, many = `${one}s`) => `${v} ${v === 1 ? one : many}`;

// What a security entry says, in plain words.
const SAID: Record<string, string> = {
  "identity.signed_in": "signed in",
  "identity.sign_in_failed": "wrong password",
  "identity.two_step_failed": "wrong two-step code",
  "identity.two_step_on": "turned on two-step sign-in",
  "identity.two_step_off": "turned off two-step sign-in",
  "identity.recovery_code_used": "used a recovery code",
  "identity.password_changed": "changed their password",
  "identity.password_set_by_link": "reset their password",
  "identity.invitation_accepted": "accepted their invitation",
  "identity.reset_requested": "asked for a password reset",
  "access.password_set": "set a password for",
  "access.person_invited": "invited",
  "access.invite_link_made": "made an invitation link for",
  "access.person_deleted": "deleted",
  "access.person_restored": "restored",
  "access.two_step_reset": "reset two-step sign-in for",
  "access.email_changed": "changed the email of",
  "company.administrator_added": "made an administrator:",
  "company.administrator_removed": "removed as administrator:",
};

/** Good morning, afternoon or evening, by the clock in Manila (the company's time zone today). */
function greeting(): string {
  const hour = Number(new Intl.DateTimeFormat("en-PH", { hour: "numeric", hourCycle: "h23", timeZone: "Asia/Manila" }).format(new Date()));
  return hour < 12 ? "Good morning!" : hour < 18 ? "Good afternoon!" : "Good evening!";
}

/** "2026-10" as the chart's label: the month, with the year on January and the first bar. */
function monthLabel(month: string, first: boolean): string {
  const [y, m] = month.split("-").map(Number);
  const name = new Date(Date.UTC(y, m - 1, 15)).toLocaleString("en-PH", { month: "short", timeZone: "UTC" });
  return first || m === 1 ? `${name} ${y}` : name;
}

function Bars({ rows, href, total }: { rows: { key: string; name: string; people: number }[]; href: string; total: number }) {
  if (rows.length === 0) return <p className="mt-3 text-sm text-ink-3">None yet.</p>;
  return (
    <ul className="mt-3 space-y-2.5">
      {rows.map((r) => (
        <li key={r.key}>
          <Link href={href} className="block rounded-md hover:bg-bench">
            <span className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate text-ink">{r.name}</span>
              <span className="shrink-0 text-ink-3">{n(r.people, "person", "people")}</span>
            </span>
            <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-rule" aria-hidden>
              <span className="block h-full rounded-full bg-sage-deep" style={{ width: `${total ? Math.min(100, Math.round((r.people / total) * 100)) : 0}%` }} />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** A card's title with "View all" on the right, as on the reference dashboard. */
function ViewAll({ href }: { href: string }) {
  return (
    <Link href={href} className="text-meta font-medium text-sage-deep hover:underline">
      View all
    </Link>
  );
}

function Share({ label, on, of }: { label: string; on: number; of: number }) {
  return (
    <li>
      <span className="flex items-baseline justify-between gap-3 text-sm">
        <span className="text-ink">{label}</span>
        <span className="shrink-0 text-ink-3 tabular-nums">
          {on} of {of}
        </span>
      </span>
      <span className="mt-1 block h-2 overflow-hidden rounded-full bg-rule" aria-hidden>
        <span className="block h-full rounded-full bg-sage-deep" style={{ width: `${of ? Math.round((on / of) * 100) : 0}%` }} />
      </span>
    </li>
  );
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

export default async function AdminHome({ searchParams }: { searchParams: Search }) {
  const account = await getAccount();
  if (!account.isCompanyAdmin) redirect("/platform/reports");
  const period = periodOf((await searchParams).period);
  const since = PERIODS.find((p) => p.value === period)!.since;
  // Never a blank page: a Platform that can't answer (unreachable, or older than this screen) is said plainly.
  const answer = loadOverview(period).then(
    (o) => ({ o, why: null as string | null }),
    (e: unknown) => ({ o: null, why: e instanceof Error ? e.message : "Bishnoi One can't be reached right now." }),
  );
  const data: Promise<Overview> = answer.then((a) => a.o ?? EMPTY_OVERVIEW);
  const first = account.fullName.split(/\s+/)[0] || account.fullName;
  const cards = [
    { label: "Active people", icon: "people", tint: TINTS.blue, href: PEOPLE },
    { label: "Signed in", icon: "account", tint: TINTS.green, href: "/platform/company/security" },
    { label: "Wrong passwords", icon: "password", tint: TINTS.orange, href: "/platform/company/activity" },
    { label: "Administrators with two-step", icon: "roles", tint: TINTS.violet, href: "/platform/company/security" },
  ] as const;

  return (
    <>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-ink-2">Hi {first},</p>
          <h1 className="text-[1.75rem] leading-tight font-semibold tracking-[-0.02em] text-ink">{greeting()}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PeriodSelect value={period} />
          <a href={`/platform/home/export?period=${period}`} download className={buttonClass("default")}>
            <Download className="size-4" aria-hidden />
            Export
          </a>
        </div>
      </header>
      <Later data={answer} fallback={null}>
        {(a) =>
          a.why ? (
            <p role="status" className="mb-4 rounded-lg border border-promo bg-promo-tint px-4 py-2.5 text-sm text-promo-ink">
              These figures couldn&apos;t be loaded: {a.why}{" "}
              {/404|not found/i.test(a.why) ? "Bishnoi One Platform is older than this screen: redeploy the Platform." : ""}{" "}
              <a href="/platform/home" className="underline">
                Try again
              </a>
            </p>
          ) : null
        }
      </Later>
      <div className="space-y-4">
        {/* The four counts of the period, each with how it moved since the period before. */}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Later data={data} fallback={cards.map((c) => <TrendCard key={c.label} icon={<Icon name={c.icon} />} tint={c.tint} label={c.label} since={since} loading />)}>
            {(o) => {
              const p = o.period;
              const admins = o.security.twoStepAdministrators;
              return (
                <>
                  <TrendCard icon={<Icon name="people" />} tint={TINTS.blue} label="Active people" value={String(o.people.active)} now={o.people.active} before={o.people.active - p.now.added} since={since} href={PEOPLE} />
                  <TrendCard icon={<Icon name="account" />} tint={TINTS.green} label="Signed in" value={String(p.now.signedIn)} now={p.now.signedIn} before={p.before.signedIn} since={since} href="/platform/company/security" />
                  <TrendCard icon={<Icon name="password" />} tint={TINTS.orange} label="Wrong passwords" value={String(p.now.failed)} now={p.now.failed} before={p.before.failed} since={since} upIsGood={false} href="/platform/company/activity" />
                  <TrendCard icon={<Icon name="roles" />} tint={TINTS.violet} label="Administrators with two-step" value={`${admins.on} of ${admins.of}`} since={since} href="/platform/company/security" />
                </>
              );
            }}
          </Later>
        </div>

        {/* By month, and people by status. */}
        <div className="grid gap-4 lg:grid-cols-3">
          <Sheet className="px-5 py-4 lg:col-span-2">
            <SectionTitle icon="trend">Sign-in activity by month</SectionTitle>
            <Later data={data} fallback={<Bone className="mt-4 h-56 w-full" />}>
              {(o) =>
                o.months.length === 0 ? (
                  <p className="mt-3 text-sm text-ink-3">No sign-ins yet.</p>
                ) : (
                  <div className="mt-3">
                    <p className="mb-2 text-meta text-ink-3">
                      {monthLabel(o.months[0].month, true)} to {monthLabel(o.months[o.months.length - 1].month, true)}
                    </p>
                    <ReportChartView
                      kind="bar"
                      labels={["People who signed in", "Wrong passwords", "People added"]}
                      points={o.months.map((m, i) => ({ x: monthLabel(m.month, i === 0), values: [m.signedIn, m.failed, m.added] }))}
                      format={(v) => String(Math.round(v))}
                      colours={SERIES}
                    />
                  </div>
                )
              }
            </Later>
          </Sheet>
          <Sheet className="px-5 py-4">
            <SectionTitle icon="people">People</SectionTitle>
            <Later data={data} fallback={<Bone className="mx-auto mt-4 size-44 rounded-full" />}>
              {(o) => (
                <div className="mt-3">
                  <Donut
                    caption="people"
                    parts={[
                      { label: "Active", value: o.people.active, colour: STATUS.active, href: PEOPLE },
                      { label: "Switched off", value: o.people.off, colour: STATUS.off, href: PEOPLE },
                      { label: "In the recycle bin", value: o.people.inBin, colour: STATUS.bin, href: `${PEOPLE}/bin` },
                    ]}
                  />
                </div>
              )}
            </Later>
          </Sheet>
        </div>

        {/* Two-step coverage, what waits on you, and the administrators. */}
        <div className="grid gap-4 lg:grid-cols-3">
          <Sheet className="px-5 py-4">
            <SectionTitle icon="password">Two-step sign-in</SectionTitle>
            <Later data={data} fallback={<div className="mt-3"><ListRows rows={2} columns={2} /></div>}>
              {(o) => {
                const all = o.security.twoStepEveryone;
                return (
                  <>
                    <p className="mt-3 text-[2.25rem] leading-none font-semibold tracking-[-0.02em] text-ink tabular-nums">{all.of ? Math.round((all.on / all.of) * 100) : 0}%</p>
                    <p className="mt-1 text-meta text-ink-3">of your people sign in with a code from their phone{o.security.required ? "; required of administrators" : ""}</p>
                    <ul className="mt-4 space-y-3">
                      <Share label="Administrators" on={o.security.twoStepAdministrators.on} of={o.security.twoStepAdministrators.of} />
                      <Share label="Everyone" on={all.on} of={all.of} />
                    </ul>
                  </>
                );
              }}
            </Later>
          </Sheet>
          <Sheet className="px-5 py-4">
            <SectionTitle icon="approvals" action={<ViewAll href={PEOPLE} />}>
              Waiting on you
            </SectionTitle>
            <Later data={data} fallback={<div className="mt-3"><ListRows rows={6} columns={2} /></div>}>
              {(o) => {
                const items = [
                  { label: "No role yet", count: o.people.noRole, href: PEOPLE },
                  { label: "No apps yet", count: o.people.noApps, href: PEOPLE },
                  { label: "Invitations waiting", count: o.signIns.invitesPending, href: PEOPLE },
                  { label: "Passwords to change", count: o.signIns.passwordsToChange, href: PEOPLE },
                  { label: "Locked out now", count: o.security.lockedNow, href: "/platform/company/security" },
                  { label: "Emails to change", count: o.security.offDomain, href: "/platform/company" },
                ];
                return (
                  <ul className="mt-2 divide-y divide-rule">
                    {items.map((i) => (
                      <li key={i.label}>
                        <Link href={i.href} className="flex items-center justify-between gap-3 py-2 text-sm hover:text-hema">
                          <span className={i.count ? "text-ink" : "text-ink-3"}>{i.label}</span>
                          {i.count ? <Pill tone="warn">{String(i.count)}</Pill> : <span className="text-meta text-ink-3">None</span>}
                        </Link>
                      </li>
                    ))}
                  </ul>
                );
              }}
            </Later>
          </Sheet>
          <Sheet className="px-5 py-4">
            <SectionTitle icon="roles" action={<ViewAll href="/platform/company" />}>
              Administrators
            </SectionTitle>
            <Later data={data} fallback={<div className="mt-3"><ListRows rows={3} columns={2} /></div>}>
              {(o) =>
                o.administrators.length === 0 ? (
                  <p className="mt-3 text-sm text-ink-3">None yet.</p>
                ) : (
                  <ul className="mt-2 divide-y divide-rule">
                    {o.administrators.map((a) => (
                      <li key={a.id} className="flex items-center gap-3 py-2.5">
                        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-bench text-meta font-semibold text-ink-2" aria-hidden>
                          {initials(a.name)}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-ink">{a.name}</span>
                          <span className="block truncate text-meta text-ink-3">{a.lastSignIn ? `Signed in ${ago(a.lastSignIn)}` : "Never signed in"}</span>
                        </span>
                        <Pill tone={a.twoStep ? "good" : o.security.required ? "bad" : "warn"}>{a.twoStep ? "Two-step on" : "No two-step"}</Pill>
                      </li>
                    ))}
                  </ul>
                )
              }
            </Later>
          </Sheet>
        </div>

        {/* Who can open what, and what happened lately. */}
        <div className="grid gap-4 lg:grid-cols-3">
          <Sheet className="px-5 py-4">
            <SectionTitle icon="apps">Access by app</SectionTitle>
            <Later data={data} fallback={<div className="mt-3"><ListRows rows={4} columns={2} /></div>}>
              {(o) => <Bars rows={o.apps} href={PEOPLE} total={o.people.active} />}
            </Later>
          </Sheet>
          <Sheet className="px-5 py-4">
            <SectionTitle icon="roles">People by role</SectionTitle>
            <Later data={data} fallback={<div className="mt-3"><ListRows rows={4} columns={2} /></div>}>
              {(o) => <Bars rows={o.roles.map((r) => ({ key: r.id, name: r.name, people: r.people }))} href="/platform/roles" total={o.people.active} />}
            </Later>
          </Sheet>
          <Sheet className="px-5 py-4">
            <SectionTitle
              icon="password"
              action={
                <Link href="/platform/company/activity" className="text-meta text-ink-2 hover:text-hema hover:underline">
                  Activity log
                </Link>
              }
            >
              Recent security
            </SectionTitle>
            <Later data={data} fallback={<div className="mt-3"><ListRows rows={5} columns={2} /></div>}>
              {(o) =>
                o.recent.length === 0 ? (
                  <Empty icon="password" title="Nothing yet">
                    Sign-ins, password changes and access changes show here.
                  </Empty>
                ) : (
                  <ul className="mt-3 divide-y divide-rule">
                    {o.recent.map((e) => (
                      <li key={e.id} className="py-2 text-sm">
                        <span className="text-ink">
                          {e.actor} {SAID[e.action] ?? e.action.replace(/[._]/g, " ")}
                          {e.target && e.target !== e.actor ? ` ${e.target}` : ""}
                        </span>
                        <span className="block text-meta text-ink-3">{ago(e.at)}</span>
                      </li>
                    ))}
                  </ul>
                )
              }
            </Later>
          </Sheet>
        </div>
      </div>
    </>
  );
}
