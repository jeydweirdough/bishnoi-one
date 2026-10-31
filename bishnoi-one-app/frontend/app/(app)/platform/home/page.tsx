import Link from "next/link";
import { redirect } from "next/navigation";
import { accountSend, getAccount } from "@/src/platform/lib/account";
import { ago } from "@/src/modules/console/lib/words";
import { FigureCard, FigureCardLoading, Tile, type Figure } from "@/src/platform/ui/figures";
import { Later } from "@/src/platform/ui/later";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ListRows } from "@/src/platform/ui/skeleton";

export const metadata = { title: "Home" };

// The Admin Console's Home (2026-10-30): user control at a glance, for the company's administrators:
// who's here, who signs in, how safe the sign-ins are, and who can open which app. Counted by the
// Platform alone (/identity/company/overview), so it's quick. No money here: the Admin Console is people.
// The page is drawn at once; the figures stream in.

type Overview = {
  people: { active: number; off: number; inBin: number; administrators: number; noRole: number; noApps: number };
  signIns: { today: number; week: number; month: number; never: number; invitesPending: number; passwordsToChange: number };
  security: {
    twoStepAdministrators: { on: number; of: number };
    twoStepEveryone: { on: number; of: number };
    required: boolean;
    failedThisWeek: number;
    lockedNow: number;
    offDomain: number;
  };
  apps: { key: string; name: string; people: number }[];
  roles: { id: string; name: string; people: number }[];
  recent: { id: string; at: string; actor: string; action: string; target: string }[];
};

const PEOPLE = "/platform/roles/people";
const EMPTY: Overview = {
  people: { active: 0, off: 0, inBin: 0, administrators: 0, noRole: 0, noApps: 0 },
  signIns: { today: 0, week: 0, month: 0, never: 0, invitesPending: 0, passwordsToChange: 0 },
  security: { twoStepAdministrators: { on: 0, of: 0 }, twoStepEveryone: { on: 0, of: 0 }, required: false, failedThisWeek: 0, lockedNow: 0, offDomain: 0 },
  apps: [],
  roles: [],
  recent: [],
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

function lead(o: Overview): Figure[] {
  const admins = o.security.twoStepAdministrators;
  const missing = admins.of - admins.on;
  return [
    { value: String(o.people.active), label: "Active people", note: `${o.people.off} switched off · ${o.people.inBin} in the recycle bin`, href: PEOPLE },
    { value: String(o.signIns.week), label: "Signed in this week", note: `${o.signIns.today} today · ${n(o.signIns.never, "person has", "people have")} never signed in`, href: "/platform/company/security" },
    {
      value: `${admins.on} of ${admins.of}`,
      label: "Administrators with two-step sign-in",
      note: `Everyone: ${o.security.twoStepEveryone.on} of ${o.security.twoStepEveryone.of}`,
      href: "/platform/company/security",
      pill: admins.of === 0 ? undefined : missing === 0 ? { text: "All protected", tone: "good" } : { text: `${missing} without`, tone: o.security.required ? "bad" : "warn" },
    },
    { value: String(o.people.administrators), label: "Administrators", note: "Who runs the company here", href: "/platform/company" },
  ];
}

function tiles(o: Overview): Figure[] {
  return [
    { value: String(o.people.noRole), label: "No role yet", note: "Each module goes by its own until given one", href: PEOPLE, alert: o.people.noRole > 0 },
    { value: String(o.people.noApps), label: "No apps yet", note: "They can sign in but open nothing", href: PEOPLE, alert: o.people.noApps > 0 },
    { value: String(o.signIns.invitesPending), label: "Invitations waiting", note: "Sent, not yet accepted", href: PEOPLE },
    { value: String(o.signIns.passwordsToChange), label: "Passwords to change", note: "Handed over; changed at their first sign-in", href: PEOPLE },
    { value: String(o.security.failedThisWeek), label: "Wrong passwords this week", note: "Tries with your people's emails", href: "/platform/company/activity", alert: o.security.failedThisWeek > 0 },
    { value: String(o.security.lockedNow), label: "Locked out now", note: "Too many wrong passwords; they wait a few minutes", href: "/platform/company/security", alert: o.security.lockedNow > 0 },
    { value: String(o.security.offDomain), label: "Emails to change", note: "Outside your email domain: they can't sign in", href: "/platform/company", alert: o.security.offDomain > 0 },
    { value: String(o.signIns.month), label: "Signed in this month", note: `Of ${o.people.active} active`, href: "/platform/company/security" },
  ];
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

export default async function AdminHome() {
  const account = await getAccount();
  if (!account.isCompanyAdmin) redirect("/platform/reports");
  // Never a blank page: a Platform that can't answer (unreachable, or older than this screen) is said plainly.
  const answer = accountSend<Overview>("GET", "/identity/company/overview").then(
    (o) => ({ o, why: null as string | null }),
    (e: unknown) => ({ o: null, why: e instanceof Error ? e.message : "Bishnoi One can't be reached right now." }),
  );
  const data = answer.then((a) => a.o ?? EMPTY);
  const leads = ["Active people", "Signed in this week", "Administrators with two-step sign-in", "Administrators"];

  return (
    <>
      <PageHeader title="Home">Your company&apos;s people at a glance: who&apos;s here, who signs in, and who can open what.</PageHeader>
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
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Later data={data} fallback={leads.map((l, i) => <FigureCardLoading key={l} label={l} first={i === 0} />)}>
            {(o) => lead(o).map((f, i) => <FigureCard key={f.label} figure={f} first={i === 0} />)}
          </Later>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Later data={data} fallback={null}>
            {(o) => tiles(o).map((f) => <Tile key={f.label} figure={f} />)}
          </Later>
        </div>
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
