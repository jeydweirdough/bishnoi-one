import Link from "next/link";
import { SuspendedTag } from "@/src/modules/console/components/organizations/record-tools";
import type { PlatformUser } from "@/src/modules/console/lib/types";

/** Can this person work right now? Their own status, and their company's. */
export function workState(u: Pick<PlatformUser, "status" | "companyStatus">): string | null {
  if (u.companyStatus === "suspended") return "Inactive: company suspended";
  if (u.status === "suspended") return "Suspended";
  return null;
}

/** "Company admin", a small stamp beside a name. */
export function AdminStamp({ label = "Company admin" }: { label?: string }) {
  return <span className="inline-flex h-5 shrink-0 items-center rounded-full bg-hema-tint px-1.5 text-stamp whitespace-nowrap text-hema uppercase">{label}</span>;
}

/** Platform users as rows: who, where, which applications as what, and whether they can work. */
export function UserRows({ users, showCompany = true }: { users: PlatformUser[]; showCompany?: boolean }) {
  return (
    <ul className="divide-y divide-rule" role="list">
      {users.map((u) => {
        const blocked = workState(u);
        return (
          <li
            key={u.id}
            className={`grid gap-1 px-5 py-3 md:items-center md:gap-4 ${showCompany ? "md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.3fr)]" : "md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"}`}
          >
            <span className="min-w-0">
              <span className="flex flex-wrap items-center gap-2">
                <Link href={`/platform/accounts/${u.id}`} className={`truncate font-semibold hover:underline ${blocked ? "text-ink-2" : "text-hema"}`}>
                  {u.fullName}
                </Link>
                {u.isCompanyAdmin && <AdminStamp />}
                {blocked && <SuspendedTag label={blocked} />}
              </span>
              <span className="block truncate text-meta text-ink-3">
                {u.email}
                {u.title && ` · ${u.title}`}
              </span>
            </span>
            {showCompany && (
              <span className="min-w-0 truncate text-meta text-ink-2">
                {u.companyName ? (
                  <Link href={`/platform/companies/${u.companyId}`} className="hover:text-hema hover:underline">
                    {u.companyName}
                  </Link>
                ) : (
                  "—"
                )}
              </span>
            )}
            <span className="min-w-0 text-meta text-ink-2">
              {u.applications && u.applications.length > 0 ? (
                u.applications.map((a, i) => (
                  <span key={a.key}>
                    {i > 0 && <span className="text-ink-3"> · </span>}
                    <span className="text-ink">{a.name}</span>
                    {a.role && <span className="text-ink-3"> as {a.role}</span>}
                  </span>
                ))
              ) : (
                <span className="text-ink-3">No applications</span>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
