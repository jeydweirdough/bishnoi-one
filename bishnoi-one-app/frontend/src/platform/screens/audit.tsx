import Link from "next/link";
import { LinkButton } from "../ui/button";
import { Empty, PageHeader, Sheet } from "../ui/sheet";
import { currentModule, enc, getCompanyMe, load } from "../lib/api";

// Every module's activity log, one screen (decided 2026-10-26, DRY): every API answers
// GET /admin/audit the same way (newest first, `before` to page, `action` or its start to
// filter), so only what is the module's own comes in as settings: its words for its actions,
// its filters, and where a record it names is opened. Each module checks its own permission
// (admin.audit) before drawing it; the API checks it again.

export type AuditEntry = { id: number; at: string; actor: string; actorId: string | null; action: string; target: string | null; targetType?: string | null; targetId?: string | null; fields: string[] };

export type AuditSettings = {
  /** The module's words for its actions ("prescription.verified": "Prescription verified"). Others are made readable. */
  words?: Record<string, string>;
  /** The filters across the top: an action, or its start ("user." for every user change); "" is everything. */
  filters: readonly { key: string; label: string }[];
  /** Where a record is opened, by its type: product → /inventory/products (then /<id>). */
  targets?: Record<string, string>;
  /** The module's own wording of an action, when it builds it rather than looks it up (the CRM's describeAudit). */
  describe?: (action: string) => string;
  /** Field names as the module says them (the CRM's describeFields). */
  fieldWords?: (fields: string[]) => string;
  /** A person's name opens their page under Users (modules that have one). */
  peoplePages?: boolean;
  /** The line under the title. */
  about?: string;
};

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

/** "prescription.needs_clarification" → "Prescription needs clarification". */
function readable(action: string): string {
  const t = action.replaceAll(/[._]/g, " ").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export async function AuditLog({ searchParams, settings }: { searchParams: Search; settings: AuditSettings }) {
  const [me, mod, s] = await Promise.all([getCompanyMe(), currentModule(), searchParams]);
  const base = `${mod?.path ?? ""}/admin/audit`;
  const action = settings.filters.find((f) => f.key === one(s.action))?.key ?? "";
  const before = one(s.before);
  const query = new URLSearchParams({ limit: "50", ...(action ? { action } : {}), ...(before ? { before } : {}) });
  const page = await load<{ items: AuditEntry[]; more: boolean }>(`/admin/audit?${query}`);
  const when = new Intl.DateTimeFormat(me.org?.locale ?? "en-PH", { dateStyle: "medium", timeStyle: "short", timeZone: me.org?.timezone ?? "Asia/Manila" });
  const here = (extra: Record<string, string> = {}) => {
    const q = new URLSearchParams({ ...(action ? { action } : {}), ...extra });
    return `${base}${q.size ? `?${q}` : ""}`;
  };
  const last = page.items.at(-1);

  return (
    <>
      <PageHeader title="Activity log">{settings.about ?? "Who did what, newest first. It names the fields that changed, never what they were changed to."}</PageHeader>
      <nav aria-label="Show" className="mb-4 flex flex-wrap gap-1.5">
        {settings.filters.map((f) => (
          <Link
            key={f.key}
            href={f.key ? `${base}?action=${enc(f.key)}` : base}
            aria-current={f.key === action ? "page" : undefined}
            className={`rounded-full border px-3 py-1 text-meta transition-colors ${
              f.key === action ? "border-sage-deep bg-mint-2 font-semibold text-ink" : "border-rule-strong bg-sheet text-ink-2 hover:border-sage-deep hover:text-ink"
            }`}
          >
            {f.label}
          </Link>
        ))}
      </nav>
      <Sheet className="px-5 pt-2 pb-3">
        {page.items.length === 0 ? (
          <Empty title={before ? "Nothing older" : "Nothing recorded yet"} icon="auditLog" />
        ) : (
          <ol className="divide-y divide-rule">
            {page.items.map((e) => {
              const list = e.targetType ? settings.targets?.[e.targetType] : undefined;
              const href = list && e.targetId ? `${list}/${e.targetId}` : null;
              return (
                <li key={e.id} className="grid gap-x-4 gap-y-0.5 py-3 sm:grid-cols-[11rem_minmax(0,1fr)]">
                  <time dateTime={e.at} className="text-meta text-ink-3 tabular-nums">
                    {when.format(new Date(e.at))}
                  </time>
                  <div className="min-w-0">
                    <p className="text-sm">
                      <span className={`font-semibold ${e.action.endsWith("sign_in_failed") ? "text-danger" : ""}`}>{settings.describe?.(e.action) ?? settings.words?.[e.action] ?? readable(e.action)}</span>
                      {e.target && e.target !== e.actor && (
                        <span className="text-ink-2">
                          {" · "}
                          {href ? (
                            <Link href={href} className="hover:text-ink hover:underline">
                              {e.target}
                            </Link>
                          ) : (
                            e.target
                          )}
                        </span>
                      )}
                    </p>
                    <p className="text-meta text-ink-3">
                      by{" "}
                      {settings.peoplePages && e.actorId ? (
                        <Link href={`${mod?.path ?? ""}/admin/users/${e.actorId}`} className="hover:text-ink hover:underline">
                          {e.actor}
                        </Link>
                      ) : (
                        e.actor
                      )}
                      {e.fields.length > 0 && <> · changed {settings.fieldWords ? settings.fieldWords(e.fields) : e.fields.join(", ")}</>}
                    </p>
                  </div>
                </li>
              );
            })}
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
