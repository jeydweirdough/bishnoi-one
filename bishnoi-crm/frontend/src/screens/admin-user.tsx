import { Particulars, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { AdminUserRow, AuditLog, UserOptions } from "@/src/platform/lib/types";
import { describeAudit } from "../components/admin/audit-words";
import { UserAccess } from "../components/admin/user-access";
import { UserForm } from "../components/admin/user-form";
import { NoAccess, OffTag, SCOPE_WORDS } from "../components/admin/words";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: (await load<AdminUserRow>(`/admin/users/${enc(id)}`)).fullName };
  } catch {
    return { title: "Person" };
  }
}

export default async function UserPage({ params }: { params: Params }) {
  const me = await getCompanyMe();
  if (!can(me, "admin.users")) return <NoAccess what="managing users" />;
  const { id } = await params;
  const [user, options, history] = await Promise.all([
    load<AdminUserRow>(`/admin/users/${enc(id)}`),
    load<UserOptions>("/admin/users/options"),
    // What they did themselves, for whoever may also read the audit log.
    can(me, "admin.audit") ? load<AuditLog>(`/admin/audit?actorId=${enc(id)}&limit=8`) : Promise.resolve(null),
  ]);
  const when = new Intl.DateTimeFormat(me.org.locale, { dateStyle: "medium", timeStyle: "short", timeZone: me.org.timezone });

  return (
    <>
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-2">
            {user.fullName}
            {!user.isActive && <OffTag />}
          </span>
        }
        crumbs={[{ href: "/admin/users", label: "Users" }]}
      >
        {user.role.name}
        {user.team ? ` in ${user.team.name}` : ""} · {SCOPE_WORDS[user.role.scope]}
      </PageHeader>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <Sheet className="px-5 pt-4 pb-6">
          <SectionTitle icon="profile">Details</SectionTitle>
          <div className="mt-4">
            <UserForm {...options} user={user} />
          </div>
        </Sheet>

        <div className="space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="password">Sign-in</SectionTitle>
            <div className="mt-3 mb-5">
              <Particulars
                items={[
                  ["Added", when.format(new Date(user.createdAt))],
                  ["Last signed in", user.lastSignInAt ? when.format(new Date(user.lastSignInAt)) : "Never"],
                ]}
              />
            </div>
            <UserAccess user={user} isMe={user.id === me.user.id} />
          </Sheet>

          {history && (
            <Sheet className="px-5 pt-4 pb-4">
              <SectionTitle icon="auditLog">Recent activity</SectionTitle>
              {history.items.length === 0 ? (
                <p className="mt-2 text-meta text-ink-3">No activity recorded.</p>
              ) : (
                <ol className="mt-2 divide-y divide-rule">
                  {history.items.map((e) => (
                    <li key={e.id} className="py-2 text-meta">
                      <p className="text-ink">
                        {describeAudit(e.action)}
                        {e.target && e.target !== user.email && <span className="text-ink-2"> · {e.target}</span>}
                      </p>
                      <time dateTime={e.at} className="text-ink-3 tabular-nums">
                        {when.format(new Date(e.at))}
                      </time>
                    </li>
                  ))}
                </ol>
              )}
            </Sheet>
          )}
        </div>
      </div>
    </>
  );
}
