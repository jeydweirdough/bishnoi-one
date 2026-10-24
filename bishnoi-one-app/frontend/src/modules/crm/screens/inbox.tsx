import { ExternalLink, Sparkles } from "lucide-react";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { LinkButton } from "@/src/platform/ui/button";
import { Pill } from "@/src/platform/ui/figures";
import { Later } from "@/src/platform/ui/later";
import { Pager } from "@/src/platform/ui/pager";
import { Bone, ListRows } from "@/src/platform/ui/skeleton";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/modules/crm/lib/access";
import { appUrl } from "@/src/platform/lib/apps";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { InboxPage } from "@/src/modules/crm/actions/inbox";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { CopyAddress, InboxList, type InboxRow } from "@/src/modules/crm/components/leads/inbox-list";

export const metadata = { title: "Lead inbox" };

const STATES = [
  { value: "new", label: "New", empty: "Nothing waiting. New enquiries from your channels show up here." },
  { value: "added", label: "Added", empty: "No leads added to the customers yet." },
  { value: "dismissed", label: "Dismissed", empty: "No dismissed leads." },
] as const;
const CHANNELS = [
  { value: "", label: "All channels" },
  { value: "facebook", label: "Facebook lead forms" },
  { value: "messenger", label: "Messenger" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "viber", label: "Viber" },
  { value: "tawkto", label: "Tawk.to" },
  { value: "form", label: "Website forms" },
];

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

/**
 * The lead inbox: people who reached the company on its own channels
 * (Facebook, Messenger, WhatsApp, Viber, Tawk.to, the website's forms), waiting
 * to be added to the customers. The channels are connected on Bishnoi One
 * Platform; whoever keeps the settings sees each one's address to give it.
 */
export default async function InboxScreen({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.inbox")) return <NoAccess what="the lead inbox" />;
  const params = await searchParams;
  const status = STATES.find((s) => s.value === one(params.status)) ?? STATES[0];
  const channel = CHANNELS.find((c) => c.value && c.value === one(params.channel))?.value ?? "";
  const page = Math.max(1, Number(one(params.page)) || 1);
  const query = new URLSearchParams({ status: status.value, ...(channel && { channel }), ...(page > 1 && { page: String(page) }) });
  const data = load<InboxPage>(`/inbox?${query}`);
  const fmt = makeFormat(me.org);
  const settings = can(me, "admin.settings");
  const href = (s: string, c = channel) => `/crm/inbox?${new URLSearchParams({ ...(s !== "new" && { status: s }), ...(c && { channel: c }) })}`;

  return (
    <>
      <PageHeader
        title="Lead inbox"
        crumbs={[{ href: "/crm/companies", label: "Customers" }]}
        actions={
          can(me, "customers.create") && (
            <LinkButton href="/crm/companies/find" icon={<Sparkles className="size-4" aria-hidden />}>
              Find leads with AI
            </LinkButton>
          )
        }
      >
        <Later data={data} fallback={<Bone className="mt-1 h-3.5 w-56" />}>
          {(d) => <>{d.counts.new === 0 ? "Nothing waiting." : `${d.counts.new} waiting to be added or dismissed.`} Enquiries from Facebook, WhatsApp, Viber, Tawk.to and your website.</>}
        </Later>
      </PageHeader>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <ToggleLinks current={status.value} options={STATES.map((s) => ({ value: s.value, label: s.label, href: href(s.value) }))} />
        <ToggleLinks current={channel} options={CHANNELS.map((c) => ({ value: c.value, label: c.label, href: href(status.value, c.value) }))} />
      </div>

      <Later
        data={data}
        fallback={
          <Sheet>
            <ListRows rows={6} columns={2} />
          </Sheet>
        }
      >
        {(d) => {
          const anyOn = d.channels.some((c) => c.on);
          const rows: InboxRow[] = d.items.map((x) => ({ ...x, when: fmt.whenLabel(x.lastAt), handledWhen: x.handledAt ? fmt.whenLabel(x.handledAt) : null }));
          return (
            <div className="space-y-4">
              <Sheet>
                {rows.length > 0 ? (
                  <InboxList rows={rows} />
                ) : !anyOn && status.value === "new" ? (
                  <Empty
                    title="No channels connected yet"
                    actions={
                      settings ? (
                        <LinkButton href={`${appUrl("platform")}/companies?q=${encodeURIComponent(me.org.slug)}`} target="_blank" icon={<ExternalLink className="size-4" aria-hidden />}>
                          Connect a channel on Bishnoi One Platform
                        </LinkButton>
                      ) : undefined
                    }
                  >
                    {settings
                      ? "Connect Facebook, WhatsApp, Viber, Tawk.to or your website on the Platform (your company → Connections). The addresses to give each one are below."
                      : "Ask your administrator to connect Facebook, WhatsApp, Viber, Tawk.to or your website."}
                  </Empty>
                ) : (
                  <Empty title={channel ? "Nothing here from this channel" : status.empty}>{channel ? "Try All channels." : undefined}</Empty>
                )}
              </Sheet>
              {d.total > d.pageSize && <Pager total={d.total} page={d.page} size={d.pageSize} base={href(status.value)} noun="leads" />}
              {settings && (
                <Sheet>
                  <div className="px-5 pt-4 sm:px-6">
                    <SectionTitle>Channels</SectionTitle>
                  </div>
                  <ul className="divide-y divide-rule">
                    {d.channels.map((c) => (
                      <li key={c.key} className="grid gap-2 px-5 py-3 sm:grid-cols-[14rem_minmax(0,1fr)_auto] sm:items-center sm:px-6">
                        <span className="font-medium text-ink">{c.name}</span>
                        <CopyAddress address={c.address} />
                        <Pill tone={c.on ? "good" : "plain"} className="justify-self-start">
                          {c.on ? "Connected" : "Not connected"}
                        </Pill>
                      </li>
                    ))}
                  </ul>
                  <p className="px-5 pb-4 text-meta text-ink-3 sm:px-6">
                    Give each channel its address (in Meta&apos;s, Viber&apos;s or Tawk.to&apos;s webhook settings, or your website&apos;s form), then fill in its secret on Bishnoi One
                    Platform: your company → Connections. Calls not signed with that secret are refused.
                  </p>
                </Sheet>
              )}
            </div>
          );
        }}
      </Later>
    </>
  );
}
