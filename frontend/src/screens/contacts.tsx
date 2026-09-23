import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { ContactRow, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { Filters, Pager } from "../components/crm/list-controls";

export const metadata = { title: "Contacts" };

const SIZE = 50;
type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function ContactsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.view")) return <NoAccess what="customers" />;
  const params = await searchParams;
  const [q, owner] = [one(params.q), one(params.owner)];
  const page = Math.max(1, Number(one(params.page)) || 1);
  const query = new URLSearchParams({ limit: String(SIZE), offset: String((page - 1) * SIZE) });
  if (q) query.set("q", q);
  if (owner) query.set("owner", owner);
  const list = await load<Paged<ContactRow>>(`/contacts?${query}`);
  const fmt = makeFormat(me.org);
  const filtered = Boolean(q || owner);
  const here = new URLSearchParams({ ...(q && { q }), ...(owner && { owner }) });

  return (
    <>
      <PageHeader
        title="Contacts"
        actions={
          can(me, "customers.create") && (
            <LinkButton href="/contacts/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add contact
            </LinkButton>
          )
        }
      >
        {list.total} {list.total === 1 ? "person" : "people"}
        {filtered ? " match" : ""}.
      </PageHeader>

      <Filters
        search="Search by name, email or company"
        selects={
          me.role?.scope !== "own"
            ? [{ name: "owner", label: "Owner", options: [{ value: "", label: "Everyone you can see" }, { value: "me", label: "Mine" }] }]
            : []
        }
      />

      <Sheet>
        {list.items.length === 0 ? (
          <Empty icon="customers" title={filtered ? "No contacts match" : "No contacts yet"}>
            {filtered ? "Try another search, or clear the filters." : "Add the people you talk to, and the company each works for."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {list.items.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/contacts/${c.id}`}
                  className="grid gap-1 px-5 py-3 hover:bg-bench/40 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,9rem)_7rem] md:items-center md:gap-4"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-semibold text-hema">{c.name}</span>
                    <span className="block truncate text-meta text-ink-3">{c.jobTitle ?? "—"}</span>
                  </span>
                  <span className="min-w-0 text-meta">
                    <span className="block truncate text-ink-2">{c.company?.name ?? "No company"}</span>
                    <span className="block truncate text-ink-3">{c.email ?? c.phone ?? c.mobile ?? ""}</span>
                  </span>
                  <span className="truncate text-meta text-ink-2">{c.owner.id === me.user.id ? "You" : c.owner.name}</span>
                  <span className="text-meta text-ink-3">{c.lastActivityAt ? fmt.whenLabel(c.lastActivityAt) : "No activity"}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      <Pager total={list.total} page={page} size={SIZE} base={`/contacts${here.size ? `?${here}` : ""}`} />
    </>
  );
}
