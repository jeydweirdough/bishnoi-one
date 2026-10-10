// Connections: how the applications reach each other. Each application keeps
// only the platform's address and its own connect key; the addresses and keys
// between applications are set here, and each one asks for its own.
import Link from "next/link";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { getStaff } from "@/src/components/gate";
import { HealthMark } from "@/src/components/marks";
import { ConnectKey, Disconnect, LinkSwitch, LinkThem, NewLinkKey, RemoveLink } from "@/src/components/connections/controls";
import type { Health } from "@/src/lib/types";
import { ago, when } from "@/src/lib/words";

export const metadata = { title: "Connections" };

type Ref = { id: string; key: string; name: string };
type App = {
  id: string;
  key: string;
  name: string;
  apiUrl: string | null;
  appUrl: string | null;
  status: Health | null;
  connected: boolean;
  keyHint: string | null;
  keyMadeAt: string | null;
  connectedAt: string | null;
};
type LinkRow = { id: string; from: Ref; to: Ref; isOn: boolean; state: "working" | "waiting" | "problem" | "off"; why: string; what: string; changedAt: string };
type Answer = { applications: App[]; links: LinkRow[]; offered: { from: Ref; to: Ref; what: string }[]; askAgainIn: number };

// A link's state, drawn with the health marks every screen uses.
const STATE: Record<LinkRow["state"], { mark: Health; label: string }> = {
  working: { mark: "operational", label: "Working" },
  waiting: { mark: "degraded", label: "Waiting" },
  problem: { mark: "down", label: "Not working" },
  off: { mark: "retired", label: "Off" },
};

/** Whether an application is connected, in a line. */
function connection(a: App): { mark: Health; text: string } {
  if (!a.connected) return { mark: "unknown", text: "Not connected yet: it asks when it first starts, or make its connect key here." };
  if (!a.connectedAt) return { mark: "degraded", text: "Key made, but it hasn't connected yet: check its API address under Applications, and that it's running." };
  const quiet = Date.now() - Date.parse(a.connectedAt) > 60 * 60 * 1000;
  return quiet ? { mark: "degraded", text: `Last connected ${ago(a.connectedAt)}. Is it running?` } : { mark: "operational", text: `Connected · asked ${ago(a.connectedAt)}` };
}

export default async function ConnectionsPage() {
  const [data, staff] = await Promise.all([load<Answer>("/platform/connections"), getStaff()]);
  const admin = staff.canAdminister;
  const minutes = Math.round(data.askAgainIn / 60);
  const working = data.links.filter((l) => l.state === "working").length;

  return (
    <>
      <PageHeader title="Connections">
        How the applications reach each other. Each one keeps only the platform&apos;s address and its own connect key; the addresses and keys between them are
        set here, and each application picks up its own within {minutes} minutes.
      </PageHeader>

      <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle icon="teams">
            Links
            <span className="ml-2 text-meta font-normal text-ink-3">
              {working} of {data.links.length} working
            </span>
          </SectionTitle>
          {data.links.length === 0 && data.offered.length === 0 ? (
            <Empty icon="teams" title="No links yet.">
              Links appear here once the applications that use each other are registered in Applications.
            </Empty>
          ) : (
            <ul className="mt-1 divide-y divide-rule">
              {data.links.map((l) => {
                const label = `${l.from.name} uses ${l.to.name}`;
                const s = STATE[l.state];
                return (
                  <li key={l.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="font-semibold">{label}</span>
                        <HealthMark status={s.mark} label={s.label} />
                      </p>
                      <p className="text-meta text-ink-2">{l.what}</p>
                      {l.state !== "working" && l.state !== "off" && <p className="mt-0.5 text-meta text-ink-3">{l.why}</p>}
                    </div>
                    {admin && (
                      <span className="flex shrink-0 items-center gap-1">
                        <LinkSwitch id={l.id} isOn={l.isOn} label={label} />
                        <NewLinkKey id={l.id} label={label} />
                        <RemoveLink id={l.id} label={label} />
                      </span>
                    )}
                  </li>
                );
              })}
              {data.offered.map((o) => {
                const label = `${o.from.name} uses ${o.to.name}`;
                return (
                  <li key={`${o.from.id}-${o.to.id}`} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="font-semibold text-ink-2">{o.from.name} can use {o.to.name}</span>
                        <span className="text-meta text-ink-3">Not linked</span>
                      </p>
                      <p className="text-meta text-ink-3">{o.what}</p>
                    </div>
                    {admin && <LinkThem fromId={o.from.id} toId={o.to.id} label={label} />}
                  </li>
                );
              })}
            </ul>
          )}
        </Sheet>

        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle icon="apps">Applications</SectionTitle>
          <p className="text-meta text-ink-3">
            Each application needs only the platform&apos;s address on its server (<code className="font-mono">PLATFORM_API_URL</code>). Its connect key is sent to
            the API address registered for it (Applications), signed, when it first asks, or when you make a new one here: nothing is copied onto its server.
          </p>
          <ul className="mt-2 divide-y divide-rule">
            {data.applications.map((a) => {
              const c = connection(a);
              return (
                <li key={a.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <Link href={`/applications/${a.id}`} className="font-semibold text-hema hover:underline">
                        {a.name}
                      </Link>
                      <HealthMark status={c.mark} label={c.text} />
                    </p>
                    <p className="text-meta text-ink-3">
                      {a.apiUrl ? (
                        <>
                          API at <span className="font-mono">{a.apiUrl}</span>
                        </>
                      ) : (
                        <>No API address, so nothing can use it: add it on its page.</>
                      )}
                      {a.keyHint && (
                        <span title={a.keyMadeAt ? when(a.keyMadeAt) : undefined}>
                          {" "}
                          · key ending <span className="font-mono">{a.keyHint}</span>, made {ago(a.keyMadeAt)}
                        </span>
                      )}
                    </p>
                  </div>
                  {admin && (
                    <span className="flex shrink-0 flex-wrap items-center justify-end gap-1">
                      <ConnectKey appId={a.id} appName={a.name} appKey={a.key} has={a.connected} />
                      {a.connected && <Disconnect appId={a.id} appName={a.name} />}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </Sheet>
      </div>
    </>
  );
}
