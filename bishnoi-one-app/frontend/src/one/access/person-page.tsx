import Link from "next/link";
import { notFound } from "next/navigation";
import { accountSend } from "@/src/platform/lib/account";
import { ApiError } from "@/src/platform/lib/api";
import { Pill } from "@/src/platform/ui/figures";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ago, when } from "@/src/modules/console/lib/words";
import { said } from "@/src/one/company/screens";
import { loadAccess } from "./load";
import { AppChips, AppRoles } from "./people";
import { PersonMenu } from "./person-dialogs";
import type { PersonPage } from "./types";

// One person in one place (2026-10-31): their details, the apps they open with their role in each, how they sign
// in and how safely, and what they did lately. Every action on them is in the menu at the top (the same as ⋯ on People).

const at = (iso: string | null) => (iso ? <span title={when(iso)}>{ago(iso)}</span> : null);

export async function PersonScreen({ id }: { id: string }) {
  const data = await loadAccess();
  if (!data) {
    return (
      <Sheet>
        <Empty icon="roles" title="For your company's administrators">
          Only your company&apos;s administrators see and change people. Ask one of them if something needs to change.
        </Empty>
      </Sheet>
    );
  }
  let p: PersonPage;
  try {
    p = await accountSend<PersonPage>("GET", `/identity/access/people/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const row = data.people.find((x) => x.id === p.id);
  const s = p.security;
  const details: [string, React.ReactNode][] = [
    ["Full name", p.fullName],
    ["Work email", p.email],
    ["Title", p.title],
    ["Status", p.status === "active" ? <Pill tone="good">Active</Pill> : <Pill tone="bad">Switched off</Pill>],
    ["Company administrator", p.isCompanyAdmin ? "Yes" : "No"],
    ["Employee ID (CRM)", p.appDetails?.crm?.employeeId ?? null],
    ["Licence number (Pharmacy)", p.appDetails?.pharmacy?.licenseNo ?? null],
    ["Finance calendar", p.appDetails?.finance?.calendarOn ? "On" : "Off"],
    ["Added", at(p.addedAt)],
  ];
  const security: [string, React.ReactNode][] = [
    ["Two-step sign-in", s.twoStep ? <Pill tone="good">On</Pill> : <Pill tone={s.twoStepRequired ? "bad" : "warn"}>{s.twoStepRequired ? "Off: required for them" : "Off"}</Pill>],
    ["Last signed in", s.lastSignIn ? at(s.lastSignIn) : "Never"],
    ["Password", !s.passwordSet ? "Not set yet" : s.mustChangePassword ? "Set by an administrator: they change it at their next sign-in" : <>Changed {at(s.passwordChangedAt) ?? "—"}</>],
    ["Open sign-ins", String(s.openSignIns)],
    ["Wrong passwords (30 days)", String(s.wrongPasswords30Days)],
    ["Locked out now", s.lockedNow ? <Pill tone="bad">Yes, for a few minutes</Pill> : "No"],
    ["Invitation", s.invitationWaiting ? "Sent, not yet accepted" : "None waiting"],
  ];
  return (
    <>
      <PageHeader
        title={p.fullName}
        crumbs={[{ href: "/platform/roles/people", label: "People" }]}
        actions={row && <PersonMenu person={row} isMe={row.id === data.meId} modules={data.modules.map((m) => m.key)} />}
      >
        {p.email}
        {p.title ? ` · ${p.title}` : ""}
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-2">
        <Sheet className="px-5 py-4">
          <SectionTitle icon="person">Details</SectionTitle>
          <div className="mt-3">
            <Particulars items={details} />
          </div>
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="password">Sign-in and security</SectionTitle>
          <div className="mt-3">
            <Particulars items={security} />
          </div>
          <p className="mt-3 text-meta text-ink-3">Set a new password, reset two-step sign-in, send an invitation or switch them off from the menu at the top.</p>
        </Sheet>
        <Sheet className="px-5 py-4 lg:col-span-2">
          <SectionTitle icon="apps">Apps and their role in each</SectionTitle>
          {row ? (
            <div className="mt-3 grid gap-4 lg:grid-cols-2">
              <AppRoles person={row} data={data} />
              <AppChips person={row} data={data} />
            </div>
          ) : (
            <p className="mt-3 text-sm text-ink-3">In the recycle bin: restore them to give apps and roles.</p>
          )}
        </Sheet>
        <Sheet className="px-5 py-4 lg:col-span-2">
          <SectionTitle
            icon="auditLog"
            action={
              <Link href={`/platform/company/activity?q=${encodeURIComponent(p.email)}`} className="text-meta text-ink-2 hover:text-hema hover:underline">
                Everything in the Activity log
              </Link>
            }
          >
            Recent activity
          </SectionTitle>
          {p.activity.length === 0 ? (
            <Empty icon="auditLog" title="Nothing yet">
              Their sign-ins, and changes by them or to them, show here.
            </Empty>
          ) : (
            <ul className="mt-3 divide-y divide-rule">
              {p.activity.map((e) => (
                <li key={e.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2 text-sm">
                  <time dateTime={e.at} title={when(e.at)} className="w-24 shrink-0 text-meta text-ink-3">
                    {ago(e.at)}
                  </time>
                  <span className="min-w-0 flex-1">
                    <span className="font-medium text-ink">{e.actor}</span> <span className="text-ink-2">{said(e.action).toLowerCase()}</span>
                    {e.target && <span className="text-ink-2">: {e.target}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
      </div>
    </>
  );
}
