import { Cable, ChevronRight, CircleCheck, CircleDashed, ExternalLink, Inbox, Sparkles } from "lucide-react";
import Link from "next/link";
import { ListFrame, UnderlineTabs } from "@/src/platform/ui/list-layout";
import { plural } from "@/src/platform/lib/format";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { LinkButton } from "@/src/platform/ui/button";
import { Later } from "@/src/platform/ui/later";
import { Pager } from "@/src/platform/ui/pager";
import { Bone, ListRows } from "@/src/platform/ui/skeleton";
import { can } from "@/src/modules/crm/lib/access";
import { appUrl } from "@/src/platform/lib/apps";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { InboxPage } from "@/src/modules/crm/actions/inbox";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { ChannelFilter, CopyAddress, InboxList, type InboxRow } from "@/src/modules/crm/components/leads/inbox-list";
import { lookOf } from "@/src/modules/crm/components/leads/channel-look";

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
  const settings = can(me, "admin.settings");
  const view = settings && one(params.view) === "channels" ? "channels" : "leads";
  const status = STATES.find((s) => s.value === one(params.status)) ?? STATES[0];
  const channel = CHANNELS.find((c) => c.value && c.value === one(params.channel))?.value ?? "";
  const page = Math.max(1, Number(one(params.page)) || 1);
  const query = new URLSearchParams({ status: status.value, ...(channel && { channel }), ...(page > 1 && { page: String(page) }) });
  const data = load<InboxPage>(`/inbox?${query}`);
  const fmt = makeFormat(me.org);
  const platform = `${appUrl("platform")}/companies?q=${encodeURIComponent(me.org.slug)}`;
  const href = (s: string, c = channel) => `/crm/inbox?${new URLSearchParams({ ...(s !== "new" && { status: s }), ...(c && { channel: c }) })}`;
  const statusTabs = (counts?: InboxPage["counts"]) =>
    STATES.map((s) => ({ href: href(s.value), label: s.label, current: s.value === status.value, count: counts?.[s.value] }));

  return (
    <>
      <PageHeader
        title="Lead inbox"
        crumbs={[{ href: "/crm/deals", label: "Sales" }]}
        actions={
          can(me, "customers.create") && (
            <LinkButton href="/crm/customers/find" icon={<Sparkles className="size-4" aria-hidden />}>
              Find leads with AI
            </LinkButton>
          )
        }
      >
        <Later data={data} fallback={<Bone className="mt-1 h-3.5 w-56" />}>
          {(d) => <>{d.counts.new === 0 ? "Nothing waiting." : `${d.counts.new} waiting to be added or dismissed.`} Enquiries from Facebook, WhatsApp, Viber, Tawk.to and your website.</>}
        </Later>
      </PageHeader>

      {/* The page in two (decided 2026-10-25): the leads to work on, and, for whoever keeps the
          settings, the channels they come from. Setting up never sits under the day's work. */}
      {settings && (
        <nav aria-label="Lead inbox" className="mb-4 flex gap-1 border-b border-rule">
          {[
            { key: "leads", label: "Leads", href: href(status.value), icon: Inbox },
            { key: "channels", label: "Channels", href: "/crm/inbox?view=channels", icon: Cable },
          ].map((t) => (
            <Link
              key={t.key}
              href={t.href}
              aria-current={view === t.key ? "page" : undefined}
              className={`-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm ${view === t.key ? "border-sage-deep font-semibold text-ink" : "border-transparent text-ink-3 hover:text-ink"}`}
            >
              <t.icon className="size-4" aria-hidden />
              {t.label}
            </Link>
          ))}
        </nav>
      )}

      {view === "channels" ? (
        <Later data={data} fallback={<Sheet><ListRows rows={5} columns={2} /></Sheet>}>
          {(d) => <Channels channels={d.channels} platform={platform} />}
        </Later>
      ) : (
        // One container for the work: where leads stand (tabs, with how many), which channel, the
        // list, and its pages at the foot.
        <ListFrame>
          <Later data={data} fallback={<UnderlineTabs tabs={statusTabs()} label="Status" />}>
            {(d) => <UnderlineTabs tabs={statusTabs(d.counts)} label="Status" />}
          </Later>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-5 py-2.5 sm:px-6">
            <ChannelFilter value={channel} options={CHANNELS} />
            <Later data={data} fallback={null}>
              {(d) =>
                !d.channels.some((c) => c.on) && settings ? (
                  <Link href="/crm/inbox?view=channels" className="inline-flex items-center gap-1.5 text-meta font-medium text-due-today hover:underline">
                    <CircleDashed className="size-3.5" aria-hidden /> No channel connected yet: set one up
                  </Link>
                ) : (
                  <span className="text-meta text-ink-3">{plural(d.total, "lead")}</span>
                )
              }
            </Later>
          </div>
          <Later data={data} fallback={<ListRows rows={6} columns={2} />}>
            {(d) => {
              const anyOn = d.channels.some((c) => c.on);
              const rows: InboxRow[] = d.items.map((x) => ({ ...x, when: fmt.whenLabel(x.lastAt), handledWhen: x.handledAt ? fmt.whenLabel(x.handledAt) : null }));
              return (
                <>
                  {rows.length > 0 ? (
                    <InboxList rows={rows} />
                  ) : !anyOn && status.value === "new" ? (
                    <Empty
                      title="No channels connected yet"
                      actions={settings ? <LinkButton href="/crm/inbox?view=channels" icon={<Cable className="size-4" aria-hidden />}>Set up a channel</LinkButton> : undefined}
                    >
                      {settings
                        ? "Connect Facebook, WhatsApp, Viber, Tawk.to or your website, and their enquiries arrive here."
                        : "Ask your administrator to connect Facebook, WhatsApp, Viber, Tawk.to or your website."}
                    </Empty>
                  ) : (
                    <Empty
                      title={channel ? "Nothing here from this channel" : status.empty}
                      source={`Your connected channels: ${d.channels.filter((c) => c.on).map((c) => c.name).join(", ") || "none yet"}. Each customer enquiry arrives here as a lead.`}
                    >
                      {channel ? "Try All channels." : undefined}
                    </Empty>
                  )}
                  {d.total > d.pageSize && (
                    <div className="border-t border-rule px-5 py-3 sm:px-6">
                      <Pager total={d.total} page={d.page} size={d.pageSize} base={href(status.value)} noun="leads" />
                    </div>
                  )}
                </>
              );
            }}
          </Later>
        </ListFrame>
      )}
    </>
  );
}

/**
 * The channels, for whoever keeps the settings (decided 2026-10-25): where each stands first, as
 * the inbox's own marks with a word beside the colour; the webhook addresses and the steps folded
 * away under Set up, opened by itself while nothing is connected yet. Connecting is on the Platform.
 */
function Channels({ channels, platform }: { channels: InboxPage["channels"]; platform: string }) {
  const on = channels.filter((c) => c.on).length;
  return (
    <Sheet>
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 sm:px-6">
        <div>
          <SectionTitle>Channels</SectionTitle>
          <p className="text-meta text-ink-3">{on === 0 ? "None connected yet: leads arrive here once one is." : `${on} of ${channels.length} connected`}</p>
        </div>
        <LinkButton href={platform} target="_blank" size="sm" icon={<ExternalLink className="size-3.5" aria-hidden />}>
          {on === 0 ? "Connect a channel" : "Manage on Platform"}
        </LinkButton>
      </div>
      <ul className="grid grid-cols-2 gap-2 px-5 py-4 sm:grid-cols-3 sm:px-6 lg:grid-cols-5">
        {channels.map((c) => {
          const look = lookOf(c.key);
          return (
            <li key={c.key} className="flex items-center gap-3 rounded-xl border border-rule px-3 py-2.5" title={c.name}>
              <span className="grid size-9 shrink-0 place-items-center rounded-xl" style={{ background: look.tint, color: look.ink }}>
                <look.icon className="size-[1.1rem]" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{look.short}</span>
                <span className={`flex items-center gap-1 text-meta ${c.on ? "font-medium text-sage-deep" : "text-ink-3"}`}>
                  {c.on ? <CircleCheck className="size-3" aria-hidden /> : <CircleDashed className="size-3" aria-hidden />}
                  {c.on ? "Connected" : "Not connected"}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      <details open={on === 0} className="group border-t border-rule">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-3 text-sm font-medium text-ink hover:bg-bench/60 sm:px-6 [&::-webkit-details-marker]:hidden">
          <ChevronRight className="size-4 text-ink-3 transition-transform group-open:rotate-90" aria-hidden />
          Set up: each channel&apos;s address
        </summary>
        <div className="px-5 pb-4 sm:px-6">
          <ol className="mb-3 grid gap-1.5 text-meta text-ink-2 sm:grid-cols-3">
            {[
              "Copy the channel's address below.",
              "Paste it in the channel's webhook settings (Meta, Viber, Tawk.to) or your website's form.",
              "Fill in its secret on Bishnoi One Platform: your company → Connections. Calls without it are refused.",
            ].map((step, i) => (
              <li key={i} className="flex gap-2 rounded-lg bg-bench px-3 py-2">
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-sheet text-[11px] font-semibold text-ink">{i + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
          <ul className="divide-y divide-rule rounded-xl border border-rule">
            {channels.map((c) => {
              const look = lookOf(c.key);
              return (
                <li key={c.key} className="grid items-center gap-2 px-3 py-2 sm:grid-cols-[11rem_minmax(0,1fr)]">
                  <span className="flex items-center gap-2 text-sm text-ink">
                    <look.icon className="size-4 shrink-0" style={{ color: look.ink }} aria-hidden />
                    {look.short}
                  </span>
                  <CopyAddress address={c.address} />
                </li>
              );
            })}
          </ul>
        </div>
      </details>
    </Sheet>
  );
}
