import { Plus } from "lucide-react";
import Link from "next/link";
import { CustomersBulk } from "../components/customers-bulk";
import { SelectAllBox, SelectBox, SelectableRow, SelectionProvider } from "@/src/platform/bulk/selection";
import { CustomerFilters } from "../components/customer-filters";
import { LinkButton } from "@/src/platform/ui/button";
import { StatusMark } from "@/src/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { listName } from "@/src/platform/lib/labels";
import { salesWorkspace, teamsFor } from "@/src/platform/lib/module";
import type { Customer, CustomerList, ListItem } from "@/src/platform/lib/types";

export const metadata = { title: "Customers" };

const PAGE_SIZE = 25;

function describe(kinds: ListItem[], c: Customer) {
  return [listName(kinds, c.kind), c.specialty, c.city].filter(Boolean).join(" · ");
}

export default async function CustomersPage({ searchParams }: { params: Promise<Record<string, never>>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const search = await searchParams;
  const [ws, me] = await Promise.all([salesWorkspace(), getCompanyMe()]);
  const fmt = makeFormat(me.org);
  const { org } = me;
  const kinds = me.lists.customer_kind;

  const pick = (key: string) => (typeof search[key] === "string" ? (search[key] as string) : "");
  const page = Math.max(1, Number(pick("page")) || 1);
  const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
  for (const key of ["q", "division", "team", "status", "kind"]) if (pick(key)) query.set(key, pick(key));

  const { items, total } = await load<CustomerList>(`/sales/customers?${query}`);
  const filtered = ["q", "division", "team", "status", "kind"].some((k) => pick(k));
  // Only worth a column when there is something to tell apart.
  const showDivision = ws.manyDivisions;
  const showTeam = ws.teams.length > 1;
  const today = fmt.todayKey();
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const can = {
    create: teamsFor(ws, "create").length > 0,
    edit: teamsFor(ws, "edit").length > 0,
    delete: teamsFor(ws, "delete").length > 0,
  };
  const bulk = can.create || can.edit || can.delete;
  // A row can be ticked when at least one bulk action could apply to it.
  const tickable = (c: Customer) => bulk && (c.can.log || c.can.edit || c.can.delete);
  const filters = Object.fromEntries(["q", "division", "team", "status", "kind"].filter((k) => pick(k)).map((k) => [k, pick(k)]));

  const pageHref = (n: number) => {
    const next = new URLSearchParams(query);
    next.delete("limit");
    next.delete("offset");
    if (n > 1) next.set("page", String(n));
    return `/customers${next.size ? `?${next}` : ""}`;
  };

  return (
    <>
      <PageHeader
        title="Customers"
        actions={
          can.create && (
            <LinkButton href="/customers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add customer
            </LinkButton>
          )
        }
      />

      <div className="mb-3">
        <CustomerFilters teams={ws.teams} divisions={showDivision ? ws.divisions.map((d) => ({ code: d.key, name: d.name })) : []} kinds={kinds} />
      </div>

      <SelectionProvider key={query.toString()} items={items.filter(tickable).map((c) => ({ id: c.id, name: c.name }))}>
        <Sheet>
          {items.length === 0 ? (
            filtered ? (
              <Empty icon="customers" title="No customers match">Try fewer words, or clear a filter.</Empty>
            ) : (
              <Empty icon="customers" title="No customers yet">Add the customers your team works with, whoever they are.</Empty>
            )
          ) : (
            <>
              {/* Wide screens: a table. */}
              <table className="hidden w-full text-left text-sm md:table">
                <thead>
                  <tr className="border-b border-rule text-caps text-ink-3 uppercase">
                    {bulk && (
                      <th scope="col" className="w-12 py-3 pl-5">
                        <SelectAllBox />
                      </th>
                    )}
                    <th scope="col" className={`${bulk ? "pl-2" : "pl-5"} py-3 pr-5 font-semibold`}>Customer</th>
                    {showDivision && <th scope="col" className="px-3 py-3 font-semibold">Division</th>}
                    {showTeam && <th scope="col" className="px-3 py-3 font-semibold">Team</th>}
                    <th scope="col" className="px-3 py-3 font-semibold">Status</th>
                    <th scope="col" className="px-3 py-3 font-semibold">Last contact</th>
                    <th scope="col" className="px-5 py-3 font-semibold">Owner</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {items.map((c) => (
                    <SelectableRow key={c.id} id={c.id} className="relative hover:bg-bench/40">
                      {bulk && <td className="py-3 pl-5 align-top">{tickable(c) && <SelectBox id={c.id} label={c.name} />}</td>}
                      <td className={`${bulk ? "pl-2" : "pl-5"} py-3 pr-5`}>
                        {/* The name link stretches over the row, so the whole row is the target. */}
                        <Link href={`/customers/${c.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                          {c.name}
                        </Link>
                        <span className="block text-meta text-ink-3">{describe(kinds, c)}</span>
                      </td>
                      {showDivision && <td className="px-3 py-3 text-ink-2">{c.divisionName}</td>}
                      {showTeam && (
                        <td className="px-3 py-3 text-ink-2">
                          {c.teamName}
                          {c.headquartersName && <span className="block text-meta text-ink-3">{c.headquartersName}</span>}
                        </td>
                      )}
                      <td className="px-3 py-3">
                        <StatusMark status={c.status} />
                      </td>
                      <td className="px-3 py-3 text-ink-2">{fmt.whenLabel(c.lastContactAt, today)}</td>
                      <td className="px-5 py-3 text-ink-2">{c.owner.name ?? "—"}</td>
                    </SelectableRow>
                  ))}
                </tbody>
              </table>

              {/* Phones: a list. */}
              <ul className="divide-y divide-rule md:hidden">
                {items.map((c) => (
                  <SelectableRow key={c.id} id={c.id} as="li" className="flex items-start">
                    {tickable(c) && (
                      <span className="pt-3 pl-4">
                        <SelectBox id={c.id} label={c.name} />
                      </span>
                    )}
                    <Link href={`/customers/${c.id}`} className="block min-w-0 flex-1 px-4 py-3">
                      <span className="flex items-start justify-between gap-3">
                        <span className="font-semibold text-hema">{c.name}</span>
                        <StatusMark status={c.status} />
                      </span>
                      <span className="block text-meta text-ink-3">{describe(kinds, c)}</span>
                      <span className="mt-0.5 block text-meta text-ink-3">
                        {showDivision && `${c.divisionName} · `}
                        {showTeam && `${c.teamName} · `}Last contact {fmt.whenLabel(c.lastContactAt, today).toLowerCase()}
                      </span>
                    </Link>
                  </SelectableRow>
                ))}
              </ul>
            </>
          )}
        </Sheet>
        {bulk && <CustomersBulk teams={ws.teams} can={can} filters={filters} total={total} org={org} />}
      </SelectionProvider>

      {total > 0 && (
        <nav aria-label="Pages" className="mt-3 flex items-center justify-between text-meta text-ink-3">
          <span>
            {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
          </span>
          {lastPage > 1 && (
            <span className="flex gap-2">
              {page > 1 && (
                <LinkButton href={pageHref(page - 1)} size="sm">
                  Previous
                </LinkButton>
              )}
              {page < lastPage && (
                <LinkButton href={pageHref(page + 1)} size="sm">
                  Next
                </LinkButton>
              )}
            </span>
          )}
        </nav>
      )}
    </>
  );
}
