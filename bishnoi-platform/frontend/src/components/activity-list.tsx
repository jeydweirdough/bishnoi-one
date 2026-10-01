import { Empty } from "@/src/platform/ui/sheet";
import { AUDIT_CATEGORIES, actionWords, ago, when } from "../lib/words";
import type { AuditEntry } from "../lib/types";

/** Audit lines as sentences: "jun@x.test suspended Bayside Clinics · 3 h ago".
 *  Used by Activity & audit, and by each company, user and application. */
export function ActivityList({ entries, showCategory = false, empty = "Nothing yet." }: { entries: AuditEntry[]; showCategory?: boolean; empty?: string }) {
  if (entries.length === 0) return <Empty title={empty} icon="auditLog" />;
  return (
    <ol className="divide-y divide-rule" role="list">
      {entries.map((e) => (
        <li key={e.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2.5">
          <span className="min-w-0 flex-1 text-sm">
            <b className="font-semibold text-ink">{e.actor}</b> <span className="text-ink-2">{actionWords(e)}</span>{" "}
            {e.target && <span className="text-ink">{e.target}</span>}
            {e.fields.length > 0 && <span className="text-meta text-ink-3"> · {e.fields.join(", ")}</span>}
          </span>
          <span className="flex shrink-0 items-baseline gap-2 text-meta text-ink-3">
            {showCategory && <span className="text-stamp uppercase">{AUDIT_CATEGORIES[e.category]}</span>}
            {/* Where a sign-in came from matters on a phone too; elsewhere it's detail. */}
            {e.address && <span className={e.category === "security" ? "" : "hidden sm:inline"}>{e.address}</span>}
            <time dateTime={e.at} title={when(e.at)}>
              {ago(e.at)}
            </time>
          </span>
        </li>
      ))}
    </ol>
  );
}
