// Activity & audit: everything done on the platform, newest first, filed four
// ways (administrative, security, support, system), and by who did it.
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { ActivityList } from "@/src/components/activity-list";
import { ActivityFilters } from "@/src/components/activity/filters";
import { Tabs } from "@/src/components/marks";
import type { AuditCategory, AuditEntry } from "@/src/lib/types";

export const metadata = { title: "Activity & audit" };

type Search = Promise<Record<string, string | string[] | undefined>>;

const TABS: { key: AuditCategory | "all"; label: string }[] = [
  { key: "all", label: "Platform activity" },
  { key: "admin", label: "Administrative actions" },
  { key: "security", label: "Security events" },
  { key: "support", label: "Support" },
  { key: "system", label: "System" },
];

const EMPTY: Record<AuditCategory | "all", string> = {
  all: "Sign-ins and every change to companies, users, applications and tickets show up here.",
  admin: "Changes to companies, users, applications, access and settings show up here.",
  security: "Sign-ins, wrong passwords, sign-outs and password changes show up here.",
  support: "Tickets logged and moved, and incidents declared and updated, show up here.",
  system: "What the platform does by itself (health checks that change an application's status, clean-ups) shows up here.",
};

const one = (v: string | string[] | undefined) => (typeof v === "string" && v.trim() ? v.trim() : "");

export default async function Page({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const category = TABS.find((t) => t.key === one(params.category))?.key ?? "all";
  const actor = one(params.actor);
  const q = one(params.q);
  const before = one(params.before);

  const query = new URLSearchParams();
  if (category !== "all") query.set("category", category);
  if (actor) query.set("actor", actor);
  if (q) query.set("q", q);
  if (before) query.set("before", before);
  const page = await load<{ entries: AuditEntry[]; more: boolean; actors: string[] }>(`/platform/activity${query.size ? `?${query}` : ""}`);

  // A link to this page with the filters kept, and some changed.
  const here = (change: Record<string, string>) => {
    const next = new URLSearchParams({
      ...(category !== "all" ? { category } : {}),
      ...(actor ? { actor } : {}),
      ...(q ? { q } : {}),
      ...change,
    });
    for (const [k, v] of [...next]) if (!v) next.delete(k);
    return `/activity${next.size ? `?${next}` : ""}`;
  };
  const last = page.entries.at(-1);
  const filtered = Boolean(actor || q);

  return (
    <>
      <PageHeader title="Activity & audit">
        Who did what on the platform, newest first. A change names the fields it touched, never what they were changed to.
      </PageHeader>

      <Tabs tabs={TABS.map((t) => ({ key: t.key, label: t.label, href: here({ category: t.key === "all" ? "" : t.key, before: "" }) }))} current={category} />

      <ActivityFilters category={category === "all" ? "" : category} actor={actor} q={q} actors={page.actors} />

      <Sheet className="px-5 pt-2 pb-3">
        {category === "security" && page.entries.length > 0 && (
          <p className="pt-2 text-meta text-ink-3">Each security event shows the address it came from.</p>
        )}
        {page.entries.length === 0 ? (
          <Empty title={before ? "Nothing older" : filtered ? "Nothing matches these filters" : "Nothing recorded yet"} icon="auditLog">
            {filtered ? "Try someone else, or fewer words." : EMPTY[category]}
          </Empty>
        ) : (
          <ActivityList entries={page.entries} showCategory={category === "all"} />
        )}
      </Sheet>

      {(page.more || before) && (
        <div className="mt-4 flex gap-2">
          {before && (
            <LinkButton href={here({ before: "" })} size="sm" variant="quiet">
              Back to the newest
            </LinkButton>
          )}
          {page.more && last && (
            <LinkButton href={here({ before: last.at })} size="sm">
              Load older
            </LinkButton>
          )}
        </div>
      )}
    </>
  );
}
