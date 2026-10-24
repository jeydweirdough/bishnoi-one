// Everyone on the platform: the people at the companies, with the
// applications each may use. And, on its own tab, the staff signed in here.
import { UserPlus } from "lucide-react";
import { LinkButton } from "@/src/modules/console/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { load } from "@/src/modules/console/platform/lib/api";
import { getStaff } from "@/src/modules/console/components/gate";
import { Tabs } from "@/src/modules/console/components/marks";
import { Filters } from "@/src/modules/console/components/organizations/filters";
import { StaffAccounts } from "@/src/modules/console/components/access/staff-accounts";
import { EndSession } from "@/src/modules/console/components/users/end-session";
import { UserRows } from "@/src/modules/console/components/users/user-rows";
import type { Options, PlatformUser, StaffSession } from "@/src/modules/console/lib/types";
import { ago, plural, when } from "@/src/modules/console/lib/words";

export const metadata = { title: "Accounts" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function UsersPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const asked = one(params.tab);
  const tab = asked === "sessions" || asked === "staff" ? asked : "users";
  const staff = await getStaff();

  return (
    <>
      <PageHeader
        title="Accounts"
        actions={
          staff.canAdminister &&
          tab === "users" && (
            <LinkButton href={one(params.company) ? `/platform/accounts/new?company=${one(params.company)}` : "/platform/accounts/new"} variant="primary" icon={<UserPlus className="size-4" aria-hidden />}>
              Add account
            </LinkButton>
          )
        }
      >
        {tab === "users"
          ? "Accounts at each company, and the modules each may open."
          : tab === "staff"
            ? "The staff who sign in to this console: Platform Admins and Support."
            : "Active staff sessions on this console."}
      </PageHeader>
      <Tabs
        current={tab}
        tabs={[
          { key: "users", label: "All accounts", href: "/platform/accounts" },
          { key: "staff", label: "Staff", href: "/platform/accounts?tab=staff" },
          { key: "sessions", label: "Staff sessions", href: "/platform/accounts?tab=sessions" },
        ]}
      />
      {tab === "users" && <AllUsers params={params} canAdd={staff.canAdminister} />}
      {tab === "staff" && (
        <div className="max-w-3xl">
          <StaffAccounts canChange={staff.canAdminister} />
        </div>
      )}
      {tab === "sessions" && <Sessions canEndOthers={staff.canAdminister} />}
    </>
  );
}

async function AllUsers({ params, canAdd }: { params: Record<string, string | string[] | undefined>; canAdd: boolean }) {
  const [q, company, application, status, admins, password] = [one(params.q), one(params.company), one(params.application), one(params.status), one(params.admins), one(params.password)];
  const query = new URLSearchParams({
    ...(q && { q }),
    ...(company && { company_id: company }),
    ...(application && { application_id: application }),
    ...(["active", "suspended"].includes(status) && { status }),
    ...(admins === "true" && { admins: "true" }),
    // The sidebar's red count on Users: people who can't sign in yet.
    ...(password === "none" && { password: "none" }),
  });
  const [{ users, total }, options] = await Promise.all([
    load<{ users: PlatformUser[]; total: number }>(`/platform/users?${query}`),
    load<Options>("/platform/options"),
  ]);
  const filtered = query.size > 0;

  return (
    <>
      <Filters
        search="Search by name or email"
        selects={[
          { name: "company", label: "Company", options: [{ value: "", label: "All companies" }, ...options.companies.map((c) => ({ value: c.id, label: c.name }))] },
          { name: "application", label: "Application", options: [{ value: "", label: "All applications" }, ...options.applications.map((a) => ({ value: a.id, label: a.name }))] },
          {
            name: "status",
            label: "Status",
            options: [
              { value: "", label: "All statuses" },
              { value: "active", label: "Active" },
              { value: "suspended", label: "Suspended" },
            ],
          },
          {
            name: "admins",
            label: "Role",
            options: [
              { value: "", label: "All accounts" },
              { value: "true", label: "Company admins only" },
            ],
          },
          {
            name: "password",
            label: "Sign-in",
            options: [
              { value: "", label: "All" },
              { value: "none", label: "No password yet" },
            ],
          },
        ]}
      />
      <p className="mb-2 text-meta text-ink-3">
        {filtered ? `${plural(users.length, "user")} found, of ${total.toLocaleString("en-PH")}.` : `${plural(total, "user")} on the platform.`}
        {users.length === 500 && " Showing the first 500; narrow the search to see the rest."}
      </p>
      <Sheet>
        {users.length === 0 ? (
          <Empty icon="people" title={filtered ? "No matching users" : "No users yet"}>
            {filtered
              ? "Try another search, or clear the filters."
              : canAdd
                ? "Add accounts with “Add account”, then grant them access to their company's applications."
                : "A Platform Admin adds users for each company."}
          </Empty>
        ) : (
          <>
            <div className="hidden gap-4 border-b border-rule px-5 py-2 text-meta text-ink-3 md:grid md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.3fr)]">
              <span>Name</span>
              <span>Company</span>
              <span>Applications</span>
            </div>
            <UserRows users={users} />
          </>
        )}
      </Sheet>
    </>
  );
}

async function Sessions({ canEndOthers }: { canEndOthers: boolean }) {
  const { sessions } = await load<{ sessions: StaffSession[] }>("/platform/sessions");
  return (
    <>
      <p className="mb-3 max-w-2xl text-meta text-ink-3">
        These are the console&apos;s staff, signed in here. Each application keeps its own users&apos; sign-ins; those aren&apos;t on the platform.
        {!canEndOthers && " You can end your own session; a Platform Admin can end any session."}
      </p>
      <Sheet>
        {sessions.length === 0 ? (
          <Empty icon="password" title="No active sessions">
            A session is listed from sign-in until it is signed out or expires.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule" role="list">
            {sessions.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-ink">{s.staff.name}</span>
                    <span className="text-meta text-ink-3">{s.staff.roleName}</span>
                    {s.isYours && <span className="rounded-full bg-hema-tint px-1.5 text-stamp text-hema uppercase">You</span>}
                  </span>
                  <span className="block text-meta text-ink-3">
                    {s.staff.email}
                    {s.address && ` · from ${s.address}`} · signed in{" "}
                    <time dateTime={s.startedAt} title={when(s.startedAt)}>
                      {ago(s.startedAt)}
                    </time>{" "}
                    · expires {when(s.expiresAt)}
                  </span>
                </span>
                {(s.isYours || canEndOthers) && <EndSession id={s.id} name={s.staff.name} yours={s.isYours} />}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
