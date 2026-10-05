// Who may reach what, at each of the three levels: requests waiting on a
// decision, which company has which application, the roles inside each
// application, and the console's own staff and what each role may do.
import { Check, Minus } from "lucide-react";
import Link from "next/link";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { getMe, load } from "@/src/platform/lib/api";
import { Decide } from "@/src/components/access/decide";
import { StaffControls } from "@/src/components/access/staff-controls";
import { getStaff } from "@/src/components/gate";
import { Count, Tabs } from "@/src/components/marks";
import { SuspendedTag } from "@/src/components/organizations/record-tools";
import type { AccessRequest, AppAccess, OrgAccess, RequestStatus, Roles } from "@/src/lib/types";
import { ago, plural, when } from "@/src/lib/words";

export const metadata = { title: "Access" };

const TABS = ["requests", "organizations", "applications", "roles"] as const;
type Tab = (typeof TABS)[number];
type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function AccessPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const tab: Tab = TABS.includes(params.tab as Tab) ? (params.tab as Tab) : "requests";
  const staff = await getStaff();
  const { pending } = await load<{ pending: number }>("/platform/access/requests?status=pending");

  return (
    <>
      <PageHeader title="Access">Who may reach what: a company&apos;s applications, a person&apos;s roles in them, and the staff who run the platform.</PageHeader>
      <Tabs
        current={tab}
        tabs={[
          { key: "requests", label: "Requests", href: "/access", count: pending },
          { key: "organizations", label: "Organization access", href: "/access?tab=organizations" },
          { key: "applications", label: "Application access", href: "/access?tab=applications" },
          { key: "roles", label: "Roles & permissions", href: "/access?tab=roles" },
        ]}
      />
      {tab === "requests" && <Requests status={typeof params.status === "string" ? params.status : "pending"} canDecide={staff.canAdminister} />}
      {tab === "organizations" && <Organizations />}
      {tab === "applications" && <Applications />}
      {tab === "roles" && <RolesTab canChange={staff.canAdminister} />}
    </>
  );
}

const REQUEST_STATES: { value: RequestStatus | "all"; label: string }[] = [
  { value: "pending", label: "Waiting" },
  { value: "approved", label: "Approved" },
  { value: "declined", label: "Declined" },
  { value: "all", label: "All" },
];

async function Requests({ status: asked, canDecide }: { status: string; canDecide: boolean }) {
  const status = REQUEST_STATES.some((s) => s.value === asked) ? asked : "pending";
  const { requests } = await load<{ requests: AccessRequest[] }>(`/platform/access/requests?status=${status}`);
  // Waiting ones first, the oldest of them at the top: they've waited longest.
  const sorted = [...requests.filter((r) => r.status === "pending").reverse(), ...requests.filter((r) => r.status !== "pending")];

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <ToggleLinks
          current={status}
          options={REQUEST_STATES.map((s) => ({ ...s, href: s.value === "pending" ? "/access" : `/access?status=${s.value}` }))}
        />
        <p className="text-meta text-ink-3">To log one for somebody, open their page under Users.</p>
      </div>
      <Sheet>
        {sorted.length === 0 ? (
          <Empty icon="approvals" title={status === "pending" ? "Nobody is waiting" : "No requests here"}>
            {status === "pending"
              ? "When somebody asks for an application, log it from their page under Users and it waits here for a Platform Admin."
              : "Try another filter."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule" role="list">
            {sorted.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start gap-x-6 gap-y-3 px-5 py-3.5">
                <div className="min-w-0 flex-1 basis-72">
                  <p className="text-sm text-ink">
                    <Link href={`/users/${r.user.id}`} className="font-semibold text-hema hover:underline">
                      {r.user.name}
                    </Link>{" "}
                    <span className="text-ink-2">at</span>{" "}
                    <Link href={`/companies/${r.company.id}`} className="text-ink hover:text-hema hover:underline">
                      {r.company.name}
                    </Link>{" "}
                    <span className="text-ink-2">wants</span> <b className="font-semibold">{r.application.name}</b>
                    {r.role && <span className="text-ink-2"> as {r.role}</span>}
                  </p>
                  {r.reason && <p className="mt-0.5 text-sm whitespace-pre-line text-ink-2">“{r.reason}”</p>}
                  <p className="mt-0.5 text-meta text-ink-3">
                    Asked{" "}
                    <time dateTime={r.createdAt} title={when(r.createdAt)}>
                      {ago(r.createdAt)}
                    </time>
                    {r.status !== "pending" && (
                      <>
                        {" · "}
                        <span className="font-semibold text-ink-2">{r.status === "approved" ? "Approved" : "Declined"}</span> by {r.decidedBy}{" "}
                        {r.decidedAt && <time dateTime={r.decidedAt}>{ago(r.decidedAt)}</time>}
                        {r.decisionNote && <>: “{r.decisionNote}”</>}
                      </>
                    )}
                  </p>
                  {r.status === "pending" && !r.companyHasApp && (
                    <p className="mt-1.5 text-meta text-ink-2">
                      {r.company.name} doesn&apos;t have {r.application.name}, so this can&apos;t be approved yet.{" "}
                      <Link href={`/companies/${r.company.id}?tab=applications`} className="font-semibold text-hema hover:underline">
                        Give {r.application.name} to {r.company.name} first
                      </Link>
                      , then come back.
                    </p>
                  )}
                </div>
                {r.status === "pending" && canDecide && <Decide request={r} canApprove={r.companyHasApp} />}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      {!canDecide && <p className="mt-3 text-meta text-ink-3">A Platform Admin approves or declines requests.</p>}
    </>
  );
}

async function Organizations() {
  const { applications, companies } = await load<OrgAccess>("/platform/access/organizations");
  if (companies.length === 0 || applications.length === 0) {
    return (
      <Sheet>
        <Empty icon="companies" title={companies.length === 0 ? "No companies yet" : "No applications yet"}>
          This shows each company against each application once there are both.
        </Empty>
      </Sheet>
    );
  }
  return (
    <>
      <p className="mb-3 max-w-2xl text-meta text-ink-3">
        A tick means the company has the application; the number is how many of its people use it. Change a company&apos;s applications on its
        Applications tab.
      </p>
      <Sheet className="overflow-x-auto">
        <table className="w-full min-w-max text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <th scope="col" className="px-5 py-2 font-normal">
                Company
              </th>
              {applications.map((a) => (
                <th key={a.id} scope="col" className="px-3 py-2 text-center font-normal">
                  {a.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {companies.map((c) => (
              <tr key={c.id}>
                <th scope="row" className="max-w-[18rem] px-5 py-2.5 text-left font-normal">
                  <span className="flex flex-wrap items-center gap-2">
                    <Link href={`/companies/${c.id}?tab=applications`} className="font-semibold text-hema hover:underline">
                      {c.name}
                    </Link>
                    {c.status === "suspended" && <SuspendedTag />}
                  </span>
                  <span className="block text-meta text-ink-3">
                    {c.admins.length === 0 ? (
                      "No company admin"
                    ) : (
                      <>
                        Run by{" "}
                        {c.admins.map((a, i) => (
                          <span key={a.id}>
                            {i > 0 && ", "}
                            <Link href={`/users/${a.id}`} className="hover:text-hema hover:underline">
                              {a.name}
                            </Link>
                          </span>
                        ))}
                      </>
                    )}
                  </span>
                </th>
                {c.cells.map((cell) => {
                  const app = applications.find((a) => a.id === cell.applicationId);
                  return (
                    <td key={cell.applicationId} className="px-3 py-2.5 text-center">
                      {cell.enabled ? (
                        <span className="inline-flex items-center gap-1 text-hema" title={`${c.name} has ${app?.name}: ${plural(cell.userCount, "user")}`}>
                          <Check className="size-4" aria-label="Has it" />
                          <span className="text-meta text-ink-2 tabular-nums">{cell.userCount}</span>
                        </span>
                      ) : (
                        <Minus className="mx-auto size-4 text-rule-strong" aria-label="Doesn't have it" />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </Sheet>
    </>
  );
}

async function Applications() {
  const { applications } = await load<AppAccess>("/platform/access/applications");
  if (applications.length === 0) {
    return (
      <Sheet>
        <Empty icon="apps" title="No applications yet">
          Register the applications under Applications; the roles people hold in each show here.
        </Empty>
      </Sheet>
    );
  }
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {applications.map((a) => (
        <Sheet key={a.id} className="self-start">
          <div className="px-5 pt-4 pb-2">
            <SectionTitle icon="apps">
              {a.name}
              <Count n={a.userCount} />
            </SectionTitle>
            <p className="text-meta text-ink-3">{a.userCount === 0 ? "Nobody uses it yet." : `${plural(a.userCount, "person", "people")} may use it.`}</p>
          </div>
          {a.roles.length > 0 && (
            <ul className="divide-y divide-rule border-t border-rule" role="list">
              {a.roles.map((r) => (
                <li key={r.role} className="flex items-baseline justify-between gap-3 px-5 py-2">
                  <Link href={`/users?application=${a.id}`} className={`text-sm hover:text-hema hover:underline ${r.role === "No role given" ? "text-ink-3" : "text-ink"}`}>
                    {r.role}
                  </Link>
                  <span className="text-meta text-ink-2 tabular-nums">{plural(r.userCount, "person", "people")}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-rule px-5 py-3">
            <p className="text-meta font-semibold text-ink-2">Application admins</p>
            {a.admins.length === 0 ? (
              <p className="text-meta text-ink-3">Nobody runs it for their company yet. Tick “Application admin” on a person&apos;s access to make one.</p>
            ) : (
              <ul className="mt-1 space-y-0.5" role="list">
                {a.admins.map((p) => (
                  <li key={p.id} className="text-sm">
                    <Link href={`/users/${p.id}`} className="text-hema hover:underline">
                      {p.name}
                    </Link>{" "}
                    <span className="text-meta text-ink-3">at {p.companyName}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Sheet>
      ))}
    </div>
  );
}

async function RolesTab({ canChange }: { canChange: boolean }) {
  const [roles, me] = await Promise.all([load<Roles>("/platform/access/roles"), getMe()]);
  const holders = roles.staffRoles.reduce((n, r) => n + r.holders.length, 0);
  const levels = [
    {
      name: "Platform Admin and Support",
      count: plural(holders, "staff member"),
      what: "The staff here. A Platform Admin changes anything on the platform; Support sees it all and works tickets and incidents.",
      href: null,
    },
    {
      name: "Company admins",
      count: plural(roles.levels.companyAdmins, "person", "people"),
      what: "Somebody at a company who runs its people and their access. Set on the person's page.",
      href: "/users?admins=true",
    },
    {
      name: "Application admins",
      count: plural(roles.levels.applicationAdmins, "grant"),
      what: "Somebody who runs one application for their company. Set on their access to that application.",
      href: "/access?tab=applications",
    },
  ];

  return (
    <div className="space-y-5">
      <Sheet className="grid divide-y divide-rule md:grid-cols-3 md:divide-x md:divide-y-0">
        {levels.map((l, i) => (
          <div key={l.name} className="px-5 py-4">
            <p className="text-meta text-ink-3">Level {i + 1}</p>
            <p className="font-semibold text-ink">{l.name}</p>
            <p className="text-sm text-ink-2">{l.href ? <Link href={l.href} className="text-hema hover:underline">{l.count}</Link> : l.count}</p>
            <p className="mt-1 text-meta text-ink-3">{l.what}</p>
          </div>
        ))}
      </Sheet>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Sheet className="self-start overflow-x-auto">
          <div className="px-5 pt-4 pb-2">
            <SectionTitle icon="roles">What each role may do here</SectionTitle>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-y border-rule text-left text-meta text-ink-3">
                <th scope="col" className="px-5 py-2 font-normal">
                  Area
                </th>
                <th scope="col" className="px-3 py-2 text-center font-normal">
                  Platform Admin
                </th>
                <th scope="col" className="px-3 py-2 text-center font-normal">
                  Support
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {roles.permissions.map((p) => (
                <tr key={`${p.area}-${p.action}`}>
                  <td className="px-5 py-2">
                    <span className="text-ink">{p.area}</span>
                    <span className="block text-meta text-ink-3">{p.action}</span>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <Check className="mx-auto size-4 text-hema" aria-label="Yes" />
                  </td>
                  <td className="px-3 py-2 text-center">
                    {p.support ? <Check className="mx-auto size-4 text-hema" aria-label="Yes" /> : <Minus className="mx-auto size-4 text-rule-strong" aria-label="No" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Sheet>

        <div className="space-y-5">
          {roles.staffRoles.map((r) => (
            <Sheet key={r.role}>
              <div className="px-5 pt-4 pb-2">
                <SectionTitle icon={r.role === "admin" ? "roles" : "support"}>
                  {r.role === "admin" ? "Platform Admins" : "Support"}
                  <Count n={r.holders.length} />
                </SectionTitle>
              </div>
              {r.holders.length === 0 ? (
                <Empty title={`Nobody is ${r.name} yet`} icon="person">
                  {r.role === "admin" ? "Make a Support member a Platform Admin below." : "Staff accounts are made with the platform's users tool."}
                </Empty>
              ) : (
                <ul className="divide-y divide-rule border-t border-rule" role="list">
                  {r.holders.map((s) => {
                    const self = s.id === me.user.id;
                    return (
                      <li key={s.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                        <span className="min-w-0 flex-1 basis-56">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className={`font-semibold ${s.isActive ? "text-ink" : "text-ink-3"}`}>{s.fullName}</span>
                            {self && <span className="rounded-[2px] bg-hema-tint px-1.5 text-stamp text-hema uppercase">You</span>}
                            {!s.isActive && <SuspendedTag label="Switched off" />}
                          </span>
                          <span className="block truncate text-meta text-ink-3">
                            {s.email} · last signed in {ago(s.lastSignInAt)}
                            {s.activeSessions > 0 && ` · ${plural(s.activeSessions, "session")} open`}
                          </span>
                        </span>
                        {canChange &&
                          (self ? (
                            <span className="text-meta text-ink-3">Another Platform Admin changes your account.</span>
                          ) : (
                            <StaffControls person={s} />
                          ))}
                      </li>
                    );
                  })}
                </ul>
              )}
            </Sheet>
          ))}
        </div>
      </div>
    </div>
  );
}
