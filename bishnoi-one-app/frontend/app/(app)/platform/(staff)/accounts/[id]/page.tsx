// One person on the platform: who they are, where they work, the
// applications they may use and as what, what they've asked for and reported,
// and what was done to their account.
import type { Metadata } from "next";
import Link from "next/link";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { enc, load } from "@/src/modules/console/platform/lib/api";
import { ActivityList } from "@/src/modules/console/components/activity-list";
import { getStaff } from "@/src/modules/console/components/gate";
import { Count, KindMark, TicketStatusMark } from "@/src/modules/console/components/marks";
import { EditLink, SuspendedTag } from "@/src/modules/console/components/organizations/record-tools";
import { Grants } from "@/src/modules/console/components/users/grants";
import { RequestAccess } from "@/src/modules/console/components/users/request-form";
import { AdminStamp, workState } from "@/src/modules/console/components/users/user-rows";
import { DeleteUser, MakePassword, SuspendUser } from "@/src/modules/console/components/users/user-tools";
import type { Options, PlatformUserDetail, RequestStatus } from "@/src/modules/console/lib/types";
import { ago, when } from "@/src/modules/console/lib/words";

type Props = { params: Promise<{ id: string }> };

const getUser = (id: string) => load<{ user: PlatformUserDetail }>(`/platform/users/${enc(id)}`).then((b) => b.user);

const REQUEST_WORDS: Record<RequestStatus, string> = { pending: "Pending", approved: "Approved", declined: "Declined" };

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
        crumbs={[{ href: "/platform/accounts", label: "Users" }]}
        title={user.fullName}
        tools={
          <>
            {user.isCompanyAdmin && <AdminStamp />}
            {blocked && <SuspendedTag label={blocked} />}
            {staff.canAdminister && (
              <>
                <EditLink href={`/platform/accounts/${user.id}/edit`} what={user.fullName} />
                <MakePassword id={user.id} name={user.fullName} hasPassword={user.hasPassword} />
                <SuspendUser id={user.id} name={user.fullName} status={user.status} />
                <DeleteUser id={user.id} name={user.fullName} />
              </>
            )}
          </>
        }
      >
        {user.no && <span className="tabular-nums">No. {user.no} · </span>}
        {user.title ? `${user.title} at ` : "At "}
        <Link href={`/platform/companies/${user.companyId}`} className="text-hema hover:underline">
          {user.companyName ?? "their company"}
        </Link>
        {user.companyStatus === "suspended" && <span className="text-danger">, which is suspended: the user has no access until it is reactivated</span>}.
      </PageHeader>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="space-y-5">
          <Sheet>
            <div className="px-5 pt-4 pb-2">
              <SectionTitle icon="apps">
                Applications
                <Count n={user.applications.length} />
              </SectionTitle>
              <p className="text-meta text-ink-3">Limited to the applications assigned to {user.companyName ?? "their company"}. Each application has its own sign-in.</p>
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
              <Empty title="No access requests" icon="approvals">
                When {user.fullName.split(" ")[0]} requests an application, log it here for a Platform Admin to review.
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
                      <span className={r.status === "pending" ? "font-semibold text-ink" : ""}>{REQUEST_WORDS[r.status]}</span> · requested{" "}
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
                <p className="text-meta text-ink-3">Every application is assigned or pending.</p>
              )}
            </div>
            {waiting.size > 0 && (
              <p className="border-t border-rule px-5 py-2.5 text-meta text-ink-3">
                Waiting for a Platform Admin's decision.
              </p>
            )}
          </Sheet>

          <Sheet>
            <div className="px-5 pt-4 pb-2">
              <SectionTitle icon="support">
                Reported tickets
                <Count n={user.tickets.length} />
              </SectionTitle>
            </div>
            {user.tickets.length === 0 ? (
              <Empty title="No tickets reported" icon="support">
                Complaints, bugs and questions from {user.fullName.split(" ")[0]} show here.
              </Empty>
            ) : (
              <ul className="divide-y divide-rule border-t border-rule" role="list">
                {user.tickets.map((t) => (
                  <li key={t.id}>
                    <div className="block px-5 py-2.5 hover:bg-bench/40">
                      <span className="flex flex-wrap items-baseline gap-x-2">
                        <span className="text-meta text-ink-3">{t.number}</span>
                        <span className={`min-w-0 font-semibold ${t.isOpen ? "text-ink" : "text-ink-2"}`}>{t.title}</span>
                      </span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-x-3">
                        <TicketStatusMark status={t.status} />
                        <KindMark kind={t.kind} />
                        <span className="text-meta text-ink-3">{ago(t.createdAt)}</span>
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        </div>

        <div className="space-y-5">
          <Sheet className="px-5 py-4">
            <SectionTitle icon="particulars">Details</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  ["Email", <a key="e" href={`mailto:${user.email}`} className="text-hema hover:underline">{user.email}</a>],
                  ["Title", user.title],
                  [
                    "Company",
                    <Link key="c" href={`/platform/companies/${user.companyId}`} className="text-hema hover:underline">
                      {user.companyName ?? "—"}
                    </Link>,
                  ],
                  ["Company admin", user.isCompanyAdmin ? "Yes, manages the company's users and access" : "No"],
                  ["Status", blocked ?? "Active"],
                  ["Last active", user.lastActiveAt ? when(user.lastActiveAt) : "Never"],
                  ["Created on", when(user.createdAt)],
                ]}
              />
            </div>
          </Sheet>
          <Sheet className="px-5 py-4">
            <SectionTitle icon="auditLog">Account activity</SectionTitle>
            <div className="mt-2">
              <ActivityList entries={user.activity} empty="No activity yet." />
            </div>
          </Sheet>
        </div>
      </div>
    </>
  );
}
