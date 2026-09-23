import { Plus } from "lucide-react";
import { ActivityFeed } from "../components/activity-feed";
import { DeleteCustomer } from "../components/delete-customer";
import { FollowUpsPanel } from "../components/follow-ups-panel";
import { LogActivity } from "../components/log-activity";
import { QuotesPanel } from "../components/quotes-panel";
import { Timeline } from "../components/timeline";
import { LinkButton } from "@/src/platform/ui/button";
import { StatusMark } from "@/src/platform/ui/marks";
import { PageHeader, Particulars, SectionTitle, Subheading, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { listName } from "@/src/platform/lib/labels";
import { salesWorkspace } from "@/src/platform/lib/module";
import type { CustomerDetail } from "@/src/platform/lib/types";

export async function generateMetadata({ params }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  const customer = await load<CustomerDetail>(`/sales/customers/${enc(id)}`);
  return { title: customer.name };
}

export default async function CustomerPage({ params }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  const [ws, me, customer] = await Promise.all([
    salesWorkspace(),
    getCompanyMe(),
    load<CustomerDetail>(`/sales/customers/${enc(id)}`),
  ]);
  // Who a follow-up can be given to: the customer's own team, wherever it is.
  const people = customer.can.log
    ? await load<{ id: string; name: string }[]>(
        `/sales/people?division=${enc(customer.division)}&team=${enc(customer.team)}`,
      )
    : [];
  const fmt = makeFormat(me.org);
  const today = fmt.todayKey();
  const self = { id: me.user.id, name: me.user.fullName };

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/customers", label: "Customers" }]}
        title={customer.name}
        actions={
          <>
            {/* The common next step, at the top where it's reached first. */}
            {customer.can.log && (
              <LinkButton href={`/customers/${id}/quotes/new`} icon={<Plus className="size-4" aria-hidden />}>
                New quote
              </LinkButton>
            )}
            {customer.can.edit && <LinkButton href={`/customers/${id}/edit`}>Edit</LinkButton>}
            {customer.can.delete && <DeleteCustomer id={id} name={customer.name} />}
          </>
        }
      >
        <span className="inline-flex flex-wrap items-center gap-2">
          <StatusMark status={customer.status} />
          <span>
            {[
              listName(me.lists.customer_kind, customer.kind),
              customer.specialty,
              ws.manyDivisions ? customer.divisionName : null,
              customer.teamName,
              customer.headquartersName,
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </span>
      </PageHeader>

      {/* Phones: details, log, follow-ups, quotes, history. Wide screens: two columns. */}
      {/* The log form and the history share one feed, so a logged call shows at once. */}
      <ActivityFeed activities={customer.activities}>
        <div className="flex flex-col gap-5 lg:grid lg:grid-cols-[minmax(0,1fr)_23rem] lg:items-start">
          <div className="contents lg:block lg:space-y-5">
            <Sheet className="order-1 px-5 py-5">
              <SectionTitle icon="particulars">Particulars</SectionTitle>
              <div className="mt-2">
                <Particulars
                  items={[
                    ["Phone", customer.phone && <a href={`tel:${customer.phone.replace(/[^\d+]/g, "")}`} className="text-hema hover:underline">{customer.phone}</a>],
                    ["Email", customer.email && <a href={`mailto:${customer.email}`} className="text-hema hover:underline">{customer.email}</a>],
                    ["Address", customer.address],
                    ["City", customer.city],
                    ["Owner", customer.owner.name],
                    ["Last contact", customer.lastContactAt && fmt.whenLabel(customer.lastContactAt, today)],
                    ["Added", fmt.whenLabel(customer.createdAt, today)],
                  ]}
                />
              </div>
              {customer.notes && (
                <div className="mt-5 border-t border-rule pt-4">
                  <Subheading>Notes</Subheading>
                  <p className="mt-1 whitespace-pre-line text-ink-2">{customer.notes}</p>
                </div>
              )}
            </Sheet>

            <Sheet className="order-4 px-5 pt-4 pb-3">
              <SectionTitle icon="quotes">Quotes</SectionTitle>
              <QuotesPanel customerHref={`/customers/${id}`} quotes={customer.quotes} canAdd={customer.can.log} />
            </Sheet>

            <Sheet className="order-5 px-5 pt-4 pb-2">
              <SectionTitle icon="history">History</SectionTitle>
              <Timeline today={today} org={me.org} kinds={me.lists.activity_kind} outcomes={me.lists.outcome} />
            </Sheet>
          </div>

          <div className="contents lg:block lg:space-y-5">
            {customer.can.log && (
              <Sheet className="order-2 px-5 pt-4 pb-5">
                <SectionTitle icon="logActivity">Log what happened</SectionTitle>
                <div className="mt-2">
                  <LogActivity
                                        customerId={id}
                    people={people}
                    me={self}
                    org={me.org}
                    kinds={me.lists.activity_kind}
                    outcomes={me.lists.outcome}
                  />
                </div>
              </Sheet>
            )}
            <Sheet className="order-3 px-5 pt-4 pb-3">
              <SectionTitle icon="followUps">Follow-ups</SectionTitle>
              <FollowUpsPanel
                                customerId={id}
                followUps={customer.followUps}
                today={today}
                people={people}
                me={self}
                canAdd={customer.can.log}
                org={me.org}
              />
            </Sheet>
          </div>
        </div>
      </ActivityFeed>
    </>
  );
}
