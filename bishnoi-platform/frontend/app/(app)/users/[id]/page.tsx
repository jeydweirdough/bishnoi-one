// One person on the platform: who they are, where they work, the
// applications they may use and as what, what they've asked for and reported,
// and what was done to their account.
import type { Metadata } from "next";
import Link from "next/link";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { ActivityList } from "@/src/components/activity-list";
import { getStaff } from "@/src/components/gate";
import { Count, KindMark, TicketStatusMark } from "@/src/components/marks";
import { EditLink, SuspendedTag } from "@/src/components/organizations/record-tools";
import { Grants } from "@/src/components/users/grants";
import { RequestAccess } from "@/src/components/users/request-form";
import { AdminStamp, workState } from "@/src/components/users/user-rows";
import { MakePassword, SuspendUser } from "@/src/components/users/user-tools";
import type { Options, PlatformUserDetail, RequestStatus } from "@/src/lib/types";
import { ago, when } from "@/src/lib/words";

type Props = { params: Promise<{ id: string }> };

const getUser = (id: string) => load<{ user: PlatformUserDetail }>(`/platform/users/${enc(id)}`).then((b) => b.user);

const REQUEST_WORDS: Record<RequestStatus, string> = { pending: "Waiting", approved: "Approved", declined: "Declined" };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: (await getUser(id)).fullName };
}

export default async function UserPage({ params }: Props) {
  const { id } = await params;
  const [user, staff, options] = await Promise.all([getUser(id), getStaff(), load<Options>("/platform/options")]);
  const blocked = workState(user);
  const has = new Set(user.applications.map((g) => g.applicationId));
  const waiting = new Set(user.requests.filter((r) => r.status === "pending").map((r) => r.applicationId));
  const askable = options.applications.filter((a) => !has.has(a.id) && !waiting.has(a.id));
  const companyApps = user.canBeGiven.map((a) => a.id);

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/users", label: "Users" }]}
        title={user.fullName}
        tools={
          <>
            {user.isCompanyAdmin && <AdminStamp />}
            {blocked && <SuspendedTag label={blocked} />}
            {staff.canAdminister && (
              <>
                <EditLink href={`/users/${user.id}/edit`} what={user.fullName} />
                <MakePassword id={user.id} name={user.fullName} hasPassword={user.hasPassword} />
                <SuspendUser id={user.id} name={user.fullName} status={user.status} />
              </>
            )}
          </>
        }
      >
        {user.title ? `${user.title} at ` : "At "}
        <Link href={`/companies/${user.companyId}`} className="text-hema hover:underline">
          {user.companyName ?? "their company"}
        </Link>
        {user.companyStatus === "suspended" && <span className="text-danger">, which is suspended: they can&apos;t work until it&apos;s reactivated</span>}.
      </PageHeader>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="space-y-5">
          <Sheet>
            <div className="px-5 pt-4 pb-2">
              <SectionTitle icon="apps">
                Applications
                <Count n={user.applications.length} />
              </SectionTitle>
              <p className="text-meta text-ink-3">They can only have what {user.companyName ?? "their company"} has. Each application still has its own sign-in.</p>
            </div>
            <div className="border-t border-rule">
              <Grants user={user} canChange={staff.canAdminister} />
            </div>
          </Sheet>

          <Sheet>
            <div className="px-5 pt-4 pb-2">
              <SectionTitle icon="approvals">
                Access requests
                <Count n={user.requests.length} />
              </SectionTitle>
            </div>
            {user.requests.length === 0 ? (
              <Empty title="Nothing asked for" icon="approvals">
                When {user.fullName.split(" ")[0]} asks for an application, log it here so a Platform Admin can decide.
              </Empty>
            ) : (
              <ul className="divide-y divide-rule border-t border-rule" role="list">
                {user.requests.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 px-5 py-2.5">
                    <span className="text-sm text-ink">
                      <b className="font-semibold">{r.applicationName}</b>
                      {r.role && <span className="text-ink-2"> as {r.role}</span>}
                    </span>
                    <span className="text-meta text-ink-3">
                      <span className={r.status === "pending" ? "font-semibold text-ink" : ""}>{REQUEST_WORDS[r.status]}</span> · asked{" "}
                      <time dateTime={r.createdAt} title={when(r.createdAt)}>
                        {ago(r.createdAt)}
                      </time>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div className="border-t border-rule px-5 py-3">
              {askable.length > 0 ? (
                <RequestAccess userId={user.id} name={user.fullName} applications={askable} companyApps={companyApps} />
              ) : (
                <p className="text-meta text-ink-3">They have, or are waiting on, every application.</p>
              )}
            </div>
            {waiting.size > 0 && (
              <p className="border-t border-rule px-5 py-2.5 text-meta text-ink-3">
                <Link href="/access" className="text-hema hover:underline">
                  Decide waiting requests under Access
                </Link>
              </p>
            )}
          </Sheet>

          <Sheet>
            <div className="px-5 pt-4 pb-2">
              <SectionTitle icon="support">
                Tickets they reported
                <Count n={user.tickets.length} />
              </SectionTitle>
            </div>
            {user.tickets.length === 0 ? (
              <Empty title="Nothing reported" icon="support">
                Complaints, bugs and questions from {user.fullName.split(" ")[0]} show here.
              </Empty>
            ) : (
              <ul className="divide-y divide-rule border-t border-rule" role="list">
                {user.tickets.map((t) => (
                  <li key={t.id}>
                    <Link href={`/support/${t.id}`} className="block px-5 py-2.5 hover:bg-bench/40">
                      <span className="flex flex-wrap items-baseline gap-x-2">
                        <span className="text-meta text-ink-3">{t.number}</span>
                        <span className={`min-w-0 font-semibold ${t.isOpen ? "text-ink" : "text-ink-2"}`}>{t.title}</span>
                      </span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-x-3">
                        <TicketStatusMark status={t.status} />
                        <KindMark kind={t.kind} />
                        <span className="text-meta text-ink-3">{ago(t.createdAt)}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        </div>

        <div className="space-y-5">
          <Sheet className="px-5 py-4">
            <SectionTitle icon="particulars">Particulars</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  ["Email", <a key="e" href={`mailto:${user.email}`} className="text-hema hover:underline">{user.email}</a>],
                  ["Title", user.title],
                  [
                    "Company",
                    <Link key="c" href={`/companies/${user.companyId}`} className="text-hema hover:underline">
                      {user.companyName ?? "—"}
                    </Link>,
                  ],
                  ["Company admin", user.isCompanyAdmin ? "Yes, runs their company's people and access" : "No"],
                  ["Status", blocked ?? "Active"],
                  ["Last active", user.lastActiveAt ? when(user.lastActiveAt) : "Not yet"],
                  ["On the platform since", when(user.createdAt)],
                ]}
              />
            </div>
          </Sheet>
          <Sheet className="px-5 py-4">
            <SectionTitle icon="auditLog">What was done to this account</SectionTitle>
            <div className="mt-2">
              <ActivityList entries={user.activity} empty="Nothing yet." />
            </div>
          </Sheet>
        </div>
      </div>
    </>
  );
}
