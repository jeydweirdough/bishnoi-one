// Every company on the platform: who they are, how many people, which
// applications, and whether anything of theirs is open with Support.
import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { load } from "@/src/platform/lib/api";
import { getStaff } from "@/src/components/gate";
import { Filters } from "@/src/components/organizations/filters";
import { SuspendedTag } from "@/src/components/organizations/record-tools";
import type { Company } from "@/src/lib/types";
import { plural } from "@/src/lib/words";

export const metadata = { title: "Companies" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function CompaniesPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const q = one(params.q);
  const status = ["active", "suspended"].includes(one(params.status)) ? one(params.status) : "";
  const query = new URLSearchParams({ ...(q && { q }), ...(status && { status }) });
  const [{ companies }, staff] = await Promise.all([load<{ companies: Company[] }>(`/platform/companies?${query}`), getStaff()]);
  const filtered = Boolean(q || status);
  const link = (s: string) => {
    const next = new URLSearchParams({ ...(q && { q }), ...(s && { status: s }) });
    return `/companies${next.size ? `?${next}` : ""}`;
  };

  return (
    <>
      <PageHeader
        title="Companies"
        actions={
          staff.canAdminister && (
            <LinkButton href="/companies/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add company
            </LinkButton>
          )
        }
      >
        {plural(companies.length, "company", "companies")}
        {filtered ? " match" : " on the platform"}.
      </PageHeader>

      <div className="flex flex-wrap items-end gap-x-4">
        <div className="min-w-0 flex-1">
          <Filters search="Search by name or company code" />
        </div>
        <div className="mb-4">
          <ToggleLinks
            current={status || "all"}
            options={[
              { value: "all", label: "All", href: link("") },
              { value: "active", label: "Active", href: link("active") },
              { value: "suspended", label: "Suspended", href: link("suspended") },
            ]}
          />
        </div>
      </div>

      <Sheet>
        {companies.length === 0 ? (
          <Empty icon="companies" title={filtered ? "No matching companies" : "No companies yet"}>
            {filtered
              ? "Try another search, or show all companies."
              : staff.canAdminister
                ? "Add the first company with “Add company”, then assign its applications and users."
                : "A Platform Admin adds companies."}
          </Empty>
        ) : (
          <>
            <div className="hidden gap-4 border-b border-rule px-5 py-2 text-meta text-ink-3 md:grid md:grid-cols-[minmax(0,1fr)_6rem_6rem_7rem]">
              <span>Company</span>
              <span className="text-right">Users</span>
              <span className="text-right">Applications</span>
              <span className="text-right">Open tickets</span>
            </div>
            <ul className="divide-y divide-rule" role="list">
              {companies.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/companies/${c.id}`}
                    className="grid gap-1 px-5 py-3 hover:bg-bench/40 md:grid-cols-[minmax(0,1fr)_6rem_6rem_7rem] md:items-center md:gap-4"
                  >
                    <span className="min-w-0">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className={`truncate font-semibold ${c.status === "suspended" ? "text-ink-2" : "text-hema"}`}>{c.name}</span>
                        {c.status === "suspended" && <SuspendedTag />}
                      </span>
                      <span className="block truncate text-meta text-ink-3">
                        {c.slug}
                        {c.status === "suspended" && " · its people can't work"}
                      </span>
                    </span>
                    <span className="flex flex-wrap gap-x-3 md:contents">
                      <span className="text-meta text-ink-2 md:text-right md:text-sm md:tabular-nums">
                        <span className="md:hidden">{plural(c.userCount, "user")}</span>
                        <span className="hidden md:inline">{c.userCount}</span>
                      </span>
                      <span className="text-meta text-ink-2 md:text-right md:text-sm md:tabular-nums">
                        <span className="md:hidden">{plural(c.appCount, "application")}</span>
                        <span className="hidden md:inline">{c.appCount}</span>
                      </span>
                      <span className={`text-meta md:text-right md:text-sm md:tabular-nums ${c.openTickets ? "font-semibold text-ink" : "text-ink-3"}`}>
                        <span className="md:hidden">{plural(c.openTickets, "open ticket")}</span>
                        <span className="hidden md:inline">{c.openTickets}</span>
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </Sheet>
    </>
  );
}
