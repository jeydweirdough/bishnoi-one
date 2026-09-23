import { Plus } from "lucide-react";
import Link from "next/link";
import { Avatar } from "@/src/platform/ui/avatar";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { AdminUserRow } from "@/src/platform/lib/types";
import { NoAccess, OffTag } from "../components/admin/words";

export const metadata = { title: "Users" };

type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function AdminUsersPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "admin.users")) return <NoAccess what="managing users" />;
  const { team } = await searchParams;
  const everyone = await load<AdminUserRow[]>("/admin/users");
  // Teams → "3 people" lands here, filtered to that team.
  const inTeam = typeof team === "string" ? everyone.find((p) => p.team?.id === team)?.team : undefined;
  const people = inTeam ? everyone.filter((p) => p.team?.id === inTeam.id) : everyone;
  const active = people.filter((p) => p.isActive).length;
  const when = new Intl.DateTimeFormat(me.org.locale, { dateStyle: "medium", timeZone: me.org.timezone });

  return (
    <>
      <PageHeader
        title={inTeam ? `Users · ${inTeam.name}` : "Users"}
        actions={
          <LinkButton href="/admin/users/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
            Add person
          </LinkButton>
        }
      >
        {active} active{people.length > active ? ` · ${people.length - active} switched off` : ""}. Each person has one role, and may be in
        one team.
        {inTeam && (
          <>
            {" "}
            <Link href="/admin/users" className="text-hema hover:underline">
              Show everyone
            </Link>
          </>
        )}
      </PageHeader>

      <Sheet>
        {people.length === 0 ? (
          <Empty icon="people" title={inTeam ? "Nobody in this team" : "No one yet"} />
        ) : (
          <ul className="divide-y divide-rule">
            {people.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/admin/users/${p.id}`}
                  className="grid gap-1 px-5 py-3 hover:bg-bench/40 md:grid-cols-[minmax(0,17rem)_minmax(0,1fr)_auto] md:items-center md:gap-5"
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <Avatar name={p.fullName} id={p.id} photoAt={null} size="md" className={p.isActive ? "" : "opacity-60"} />
                    <span className="min-w-0">
                      <span className={`block truncate font-semibold ${p.isActive ? "text-hema" : "text-ink-3"}`}>
                        {p.fullName}
                        {p.id === me.user.id && <span className="font-normal text-ink-3"> (you)</span>}
                      </span>
                      <span className="block truncate text-meta text-ink-3">{p.email}</span>
                    </span>
                  </span>
                  <span className="min-w-0 text-meta text-ink-2">
                    <span className="font-medium text-ink">{p.role.name}</span>
                    {p.team ? <> · {p.team.name}</> : <span className="text-ink-3"> · no team</span>}
                  </span>
                  <span className="text-meta text-ink-3">
                    {!p.isActive ? <OffTag /> : p.lastSignInAt ? `Last in ${when.format(new Date(p.lastSignInAt))}` : "Never signed in"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
