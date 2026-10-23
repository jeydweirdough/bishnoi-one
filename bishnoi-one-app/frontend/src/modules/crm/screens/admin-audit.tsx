import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { AuditLog } from "@/src/platform/lib/types";
import { AUDIT_FILTERS, describeAudit, describeFields } from "@/src/modules/crm/components/admin/audit-words";
import { NoAccess } from "@/src/modules/crm/components/admin/words";

export const metadata = { title: "Audit log" };

type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function AuditLogPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "admin.audit")) return <NoAccess what="the audit log" />;
  const { before, action } = await searchParams;
  const filter = AUDIT_FILTERS.find((f) => f.key === action)?.key ?? "";
  const query = new URLSearchParams({ limit: "50" });
  if (typeof before === "string") query.set("before", before);
  if (filter) query.set("action", filter);
  const page = await load<AuditLog>(`/admin/audit?${query}`);
  const when = new Intl.DateTimeFormat(me.org.locale, { dateStyle: "medium", timeStyle: "short", timeZone: me.org.timezone });
  const last = page.items.at(-1);
  const here = (extra: Record<string, string> = {}) => {
    const q = new URLSearchParams({ ...(filter ? { action: filter } : {}), ...extra });
    return `/crm/admin/audit${q.size ? `?${q}` : ""}`;
  };

  return (
    <>
      <PageHeader title="Audit log">
        Who changed what, newest first. It names the fields that changed, never what they were changed to.
      </PageHeader>

      <nav aria-label="Show" className="mb-4 flex flex-wrap gap-1.5">
        {AUDIT_FILTERS.map((f) => (
          <Link
            key={f.key}
            href={f.key ? `/crm/admin/audit?action=${enc(f.key)}` : "/crm/admin/audit"}
            aria-current={f.key === filter ? "page" : undefined}
            className={`rounded-md border px-3 py-1 text-meta ${
              f.key === filter ? "border-hema bg-hema-tint font-semibold text-ink" : "border-rule-strong bg-sheet text-ink-2 hover:border-hema hover:text-ink"
            }`}
          >
            {f.label}
          </Link>
        ))}
      </nav>

      <Sheet className="px-5 pt-2 pb-3">
        {page.items.length === 0 ? (
          <Empty title={before ? "Nothing older" : "Nothing recorded yet"} icon="auditLog">
            Sign-ins and changes to people, roles and teams show up here.
          </Empty>
        ) : (
          <ol className="divide-y divide-rule">
            {page.items.map((e) => (
              <li key={e.id} className="grid gap-x-4 gap-y-0.5 py-3 sm:grid-cols-[11rem_minmax(0,1fr)]">
                <time dateTime={e.at} className="text-meta text-ink-3 tabular-nums">
                  {when.format(new Date(e.at))}
                </time>
                <div className="min-w-0">
                  <p className="text-sm">
                    <span className={`font-semibold ${e.action === "auth.sign_in_failed" ? "text-danger" : ""}`}>{describeAudit(e.action)}</span>
                    {e.target && e.target !== e.actor && <span className="text-ink-2"> · {e.target}</span>}
                  </p>
                  <p className="text-meta text-ink-3">
                    by {e.actorId ? <Link href={`/crm/admin/users/${e.actorId}`} className="hover:text-ink hover:underline">{e.actor}</Link> : e.actor}
                    {e.fields.length > 0 && <> · changed {describeFields(e.fields)}</>}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Sheet>
      {(page.more || before) && (
        <div className="mt-4 flex gap-2">
          {before && (
            <LinkButton href={here()} size="sm" variant="quiet">
              Newest
            </LinkButton>
          )}
          {page.more && last && (
            <LinkButton href={here({ before: String(last.id) })} size="sm">
              Older
            </LinkButton>
          )}
        </div>
      )}
    </>
  );
}
