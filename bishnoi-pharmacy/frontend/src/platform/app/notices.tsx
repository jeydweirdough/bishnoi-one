import { Info, Megaphone, TriangleAlert, Wrench } from "lucide-react";
import { THIS_APP } from "../lib/apps";

/**
 * Announcements from Bishnoi One Platform, above every page: the ones showing now
 * for this app (or for everyone), and maintenance coming up. Platform keeps
 * them in Discord and serves them at /public/notices; PLATFORM_API_URL says
 * where Platform's API is. If Platform can't be reached, nothing shows and the
 * page carries on.
 *
 * The same file is in every app's shared kit (src/platform/app/notices.tsx).
 */

type Notice = {
  id: string;
  kind: "announcement" | "notification" | "maintenance";
  level: "info" | "warning" | "critical";
  title: string;
  body: string | null;
  startsAt: string;
  endsAt: string | null;
  state: "showing" | "scheduled";
};

const PLATFORM_API_URL = (process.env.PLATFORM_API_URL || "http://127.0.0.1:8305").replace(/\/$/, "");

// Asked at most once a minute per server. When Platform can't be reached,
// nothing shows (never an old answer, which could be something since taken
// down), and it isn't asked again for a minute, so pages don't wait on it.
let kept: { at: number; notices: Notice[] } | null = null;

async function load(): Promise<Notice[]> {
  if (kept && Date.now() - kept.at < 60_000) return kept.notices;
  let notices: Notice[] = [];
  try {
    const res = await fetch(`${PLATFORM_API_URL}/public/notices?app=${encodeURIComponent(THIS_APP || "")}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    if (res.ok) {
      const body = (await res.json()) as { notices: Notice[] };
      // Coming up: only maintenance is worth saying ahead of time.
      notices = body.notices.filter((n) => n.state === "showing" || (n.state === "scheduled" && n.kind === "maintenance"));
    }
  } catch {
    notices = [];
  }
  kept = { at: Date.now(), notices };
  return notices;
}

const TONE = {
  info: "border-hema/40 bg-hema-tint text-ink",
  warning: "border-rule-strong bg-bench text-ink",
  critical: "border-danger bg-danger-tint text-ink",
} as const;

function Icon({ n }: { n: Notice }) {
  const props = { className: `mt-0.5 size-4 shrink-0 ${n.level === "critical" ? "text-danger" : "text-hema"}`, "aria-hidden": true } as const;
  if (n.kind === "maintenance") return <Wrench {...props} />;
  if (n.level !== "info") return <TriangleAlert {...props} />;
  return n.kind === "announcement" ? <Megaphone {...props} /> : <Info {...props} />;
}

export async function Notices({ timeZone }: { timeZone?: string }) {
  const notices = await load();
  if (!notices.length) return null;
  const at = new Intl.DateTimeFormat("en-PH", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone });
  return (
    <section aria-label="Announcements" className="mb-5 space-y-2">
      {notices.map((n) => (
        <details key={n.id} className={`group rounded-[3px] border px-4 py-2.5 text-sm ${TONE[n.level]}`} open={n.level === "critical"}>
          <summary className={`flex cursor-pointer list-none items-start gap-2.5 ${n.body ? "" : "pointer-events-none"}`}>
            <Icon n={n} />
            <span className="min-w-0 flex-1">
              <span className="font-semibold">{n.title}</span>
              {n.kind === "maintenance" && (
                <span className="text-ink-2">
                  {" · "}
                  {n.state === "scheduled" ? "from " : "until "}
                  {n.state === "scheduled" ? at.format(new Date(n.startsAt)) : n.endsAt ? at.format(new Date(n.endsAt)) : "further notice"}
                  {n.state === "scheduled" && n.endsAt ? ` to ${at.format(new Date(n.endsAt))}` : ""}
                </span>
              )}
            </span>
            {n.body && <span className="shrink-0 text-meta text-hema group-open:hidden">Read</span>}
          </summary>
          {n.body && <p className="mt-1.5 pl-[1.625rem] whitespace-pre-line text-ink-2">{n.body}</p>}
        </details>
      ))}
    </section>
  );
}
