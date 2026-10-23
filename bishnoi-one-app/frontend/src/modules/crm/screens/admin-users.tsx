import { ArrowDown, ArrowUp, Plus, Upload } from "lucide-react";
import Link from "next/link";
import { Avatar } from "@/src/platform/ui/avatar";
import { LinkButton } from "@/src/platform/ui/button";
import { Pager } from "@/src/platform/ui/pager";
import { pageOf, slicePage } from "@/src/platform/ui/paging";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { USERS, can, canAny } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { AdminUserRow } from "@/src/platform/lib/types";
import { NoAccess, OffTag } from "@/src/modules/crm/components/admin/words";
import { Filters } from "@/src/modules/crm/components/crm/list-controls";
import { FigureCard } from "@/src/platform/ui/figures";

export const metadata = { title: "Users" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

const WEEK = 7 * 86_400_000;
/** Where someone stands: switched off, never signed in, signed in this week, or not lately. */
function standing(p: AdminUserRow, now: number) {
  if (!p.isActive) return { key: "off", label: "Inactive", color: "#8f98a3" };
  if (!p.lastSignInAt) return { key: "never", label: "Never signed in", color: "#d5d9df" };
  return now - Date.parse(p.lastSignInAt) < WEEK
    ? { key: "week", label: "Signed in this week", color: "#2a78d6" }
    : { key: "earlier", label: "Not signed in this week", color: "#eda100" };
}

const SORTS = {
  name: (a: AdminUserRow, b: AdminUserRow) => a.fullName.localeCompare(b.fullName),
  role: (a: AdminUserRow, b: AdminUserRow) => a.role.name.localeCompare(b.role.name) || a.fullName.localeCompare(b.fullName),
  team: (a: AdminUserRow, b: AdminUserRow) => (a.team?.name ?? "~").localeCompare(b.team?.name ?? "~") || a.fullName.localeCompare(b.fullName),
  signin: (a: AdminUserRow, b: AdminUserRow) => (b.lastSignInAt ?? "").localeCompare(a.lastSignInAt ?? ""),
  added: (a: AdminUserRow, b: AdminUserRow) => b.createdAt.localeCompare(a.createdAt),
};
type SortKey = keyof typeof SORTS;

/** Everyone who uses the CRM: three figures to act on, then a table to search, filter and sort. */
export default async function AdminUsersPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!canAny(me, USERS)) return <NoAccess what="managing users" />;
  const params = await searchParams;
  const everyone = await load<AdminUserRow[]>("/admin/users");
  const now = Date.now();
  // Teams → "3 people" lands here, filtered to that team.
  const team = one(params.team);
  const role = one(params.role);
  const status = one(params.status);
  const search = one(params.q).toLowerCase();
  const sort = (Object.keys(SORTS) as SortKey[]).find((k) => k === one(params.sort)) ?? "name";
  const reverse = one(params.desc) === "1";
  const people = everyone
    .filter((p) => (!team || p.team?.id === team || p.otherTeams.some((t) => t.id === team)) && (!role || p.role.id === role) && (!status || standing(p, now).key === status))
    .filter((p) => !search || p.fullName.toLowerCase().includes(search) || p.email.toLowerCase().includes(search) || (p.employeeId ?? "").toLowerCase().includes(search))
    .sort((a, b) => (reverse ? -1 : 1) * SORTS[sort](a, b));
  const shown = slicePage(people, pageOf(params.page));
  const active = everyone.filter((p) => p.isActive);
  const count = (key: string) => everyone.filter((p) => standing(p, now).key === key).length;
  const roles = [...new Map(everyone.map((p) => [p.role.id, p.role.name])).entries()];
  const teams = [...new Map(everyone.filter((p) => p.team).map((p) => [p.team!.id, p.team!.name])).entries()].sort((a, b) => a[1].localeCompare(b[1]));
  const when = new Intl.DateTimeFormat(me.org.locale, { dateStyle: "medium", timeZone: me.org.timezone });
  const keep = new URLSearchParams(Object.entries({ team, role, status, q: one(params.q) }).filter(([, v]) => v) as [string, string][]);
  // The page links keep the search, the filters and the order.
  const keepAll = new URLSearchParams(keep);
  if (sort !== "name") keepAll.set("sort", sort);
  if (reverse) keepAll.set("desc", "1");
  const sortHref = (k: SortKey) => {
    const q = new URLSearchParams(keep);
    if (k !== "name") q.set("sort", k);
    if (sort === k && !reverse) q.set("desc", "1");
    return `/crm/admin/users${q.size ? `?${q}` : ""}`;
  };
  const Head = ({ k, children }: { k: SortKey; children: React.ReactNode }) => (
    <th scope="col" className="px-3 py-2 font-medium first:px-5" aria-sort={sort === k ? (reverse ? "descending" : "ascending") : undefined}>
      <Link href={sortHref(k)} className="inline-flex items-center gap-1 hover:text-ink">
        {children}
        {sort === k && (reverse ? <ArrowUp className="size-3" aria-hidden /> : <ArrowDown className="size-3" aria-hidden />)}
      </Link>
    </th>
  );

  return (
    <>
      <PageHeader
        title="People and access"
        actions={
          <>
            {can(me, "admin.users") && (
              <LinkButton href="/crm/admin/users/import" icon={<Upload className="size-4" aria-hidden />}>
                Import
              </LinkButton>
            )}
            <LinkButton href="/crm/admin/users/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add person
            </LinkButton>
          </>
        }
      >
        {can(me, "admin.users")
          ? "Everyone who uses the CRM. Each person has one role, which says what they may do, and may be in one team."
          : "The people in the teams you manage: their role, their team and their details. Other roles are given by an administrator."}
      </PageHeader>

      {/* Three figures, each a filter: the few things an administrator acts on. */}
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <FigureCard first figure={{ value: String(active.length), label: "Active", note: `${count("week")} signed in this week`, href: "/crm/admin/users" }} />
        <FigureCard figure={{ value: String(count("never")), label: "Never signed in", note: count("never") ? "Send them their sign-in again" : "Everyone has signed in", alert: count("never") > 0, href: "/crm/admin/users?status=never" }} />
        <FigureCard figure={{ value: String(count("off")), label: "Inactive", note: "Can't sign in; their records stay", href: "/crm/admin/users?status=off" }} />
      </div>

      <Filters
        search="Name, email or employee ID"
        selects={[
          { name: "role", label: "Role", options: [{ value: "", label: "All roles" }, ...roles.map(([id, name]) => ({ value: id, label: name }))] },
          { name: "team", label: "Team", options: [{ value: "", label: "All teams" }, ...teams.map(([id, name]) => ({ value: id, label: name }))] },
          {
            name: "status",
            label: "Status",
            options: [
              { value: "", label: "All" },
              { value: "week", label: "Signed in this week" },
              { value: "earlier", label: "Not signed in this week" },
              { value: "never", label: "Never signed in" },
              { value: "off", label: "Inactive" },
            ],
          },
        ]}
      />

      <Sheet className="overflow-x-auto">
        <p className="border-b border-rule px-5 py-2.5 text-meta text-ink-2">
          {people.length} of {everyone.length} {everyone.length === 1 ? "person" : "people"}
        </p>
        {people.length === 0 ? (
          <div className="px-5 py-2">
            <Empty
              icon="people"
              title={everyone.length ? "Nobody matches" : "No one yet"}
              actions={
                !everyone.length && (
                  <LinkButton href="/crm/admin/users/new" variant="primary">
                    Add a person
                  </LinkButton>
                )
              }
            >
              {everyone.length ? "Clear a filter to see more." : "Add the people who use the CRM, and give each a role."}
            </Empty>
          </div>
        ) : (
          <table className="w-full min-w-[48rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-meta text-ink-3">
                <Head k="name">Person</Head>
                <Head k="role">Role</Head>
                <Head k="team">Team</Head>
                <Head k="signin">Last signed in</Head>
                <Head k="added">Added</Head>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {shown.rows.map((p) => {
                const s = standing(p, now);
                return (
                  <tr key={p.id} className="hover:bg-bench/40">
                    <td className="px-5 py-2.5">
                      <Link href={`/crm/admin/users/${p.id}`} className="flex items-center gap-2.5">
                        <Avatar name={p.fullName} id={p.id} photoAt={null} size="sm" className={p.isActive ? "" : "opacity-60"} />
                        <span className="min-w-0">
                          <span className={`block truncate font-medium hover:underline ${p.isActive ? "text-ink" : "text-ink-3"}`}>
                            {p.fullName}
                            {p.id === me.user.id && <span className="font-normal text-ink-3"> (you)</span>}
                          </span>
                          <span className="block truncate text-meta text-ink-3">{p.employeeId ? `${p.employeeId} · ${p.email}` : p.email}</span>
                        </span>
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 text-ink">{p.role.name}</td>
                    <td className="px-3 py-2.5 text-ink-2">
                      {p.team?.name ?? <span className="text-ink-3">No team</span>}
                      {p.otherTeams.length > 0 && <span className="block text-meta text-ink-3">Also {p.otherTeams.map((t) => t.name).join(", ")}</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {s.key === "off" ? (
                        <OffTag />
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-meta text-ink-2">
                          <span className="size-2 rounded-full" style={{ background: s.color }} aria-hidden />
                          {s.label}
                        </span>
                      )}
                      {p.lastSignInAt && <span className="block text-meta text-ink-3">{when.format(new Date(p.lastSignInAt))}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-meta text-ink-2">{when.format(new Date(p.createdAt))}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Sheet>
      <Pager total={people.length} page={shown.page} base={`/crm/admin/users${keepAll.size ? `?${keepAll}` : ""}`} />
    </>
  );
}
