import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { NewCustomerButton } from "../components/crm/new-customer";
import { LinkButton } from "@/src/platform/ui/button";
import { LogVisitButton } from "../components/field/log-visit";
import type { Doctors } from "../components/field/types";
import { isFieldAgent } from "../components/field/words";

export const metadata = { title: "Doctors" };

/** The doctors someone visits, most owed first: what each owes and when they were last seen. */
export default async function FieldDoctorsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "visits.view")) return <NoAccess what="doctors' balances" />;
  const { q, owed } = await searchParams;
  const search = typeof q === "string" ? q : "";
  const onlyOwed = owed === "1";
  const data = await load<Doctors>(`/field/doctors?limit=500${search ? `&search=${enc(search)}` : ""}${onlyOwed ? "&owed=true" : ""}`);
  const fmt = makeFormat(me.org);
  const today = fmt.todayKey();
  const showOwner = me.role?.scope !== "own";

  return (
    <>
      <PageHeader
        title="Doctors"
        actions={
          can(me, "visits.create") && (
            <LogVisitButton requireLocation={isFieldAgent(me)} variant="primary" org={me.org} now={new Date().toISOString()} doctors={data.items.map((d) => ({ id: d.id, name: d.name }))} />
          )
        }
      >
        {data.total} {data.total === 1 ? "doctor" : "doctors"} · {fmt.peso(data.owedCentavos)} owed in all
      </PageHeader>

      <form className="mb-4 flex flex-wrap items-center gap-3" action="/field/doctors">
        <input
          name="q"
          defaultValue={search}
          placeholder="Search by name"
          aria-label="Search doctors by name"
          className="h-9 w-64 rounded-[6px] border border-rule-strong bg-sheet px-3 text-sm hover:border-control focus:border-hema focus:outline-none"
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="owed" value="1" defaultChecked={onlyOwed} className="size-4 accent-hema" />
          Only those who owe
        </label>
        <button type="submit" className="h-9 rounded-[6px] border border-rule-strong bg-sheet px-4 text-sm font-semibold hover:border-control">
          Show
        </button>
      </form>

      <Sheet className="px-5 pt-2 pb-3">
        {data.items.length === 0 ? (
          <Empty
            title="No doctors here"
            icon="customers"
            actions={
              search || onlyOwed ? (
                <LinkButton href="/field/doctors">Clear the search</LinkButton>
              ) : (
                <>
                  {can(me, "customers.create") && (
<NewCustomerButton label="Add a doctor" kind="doctor" icon={false} />
                  )}
                  {can(me, "goals.import") && <LinkButton href="/field/balances/import">Upload balances</LinkButton>}
                </>
              )
            }
          >
            {search || onlyOwed ? "Nothing matches. Clear the search to see them all." : "Doctors are customers of the type Doctor, given to you by your lead or the admin."}
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th scope="col" className="py-2 pr-3 font-semibold">Doctor</th>
                  {showOwner && <th scope="col" className="px-3 py-2 font-semibold">Visited by</th>}
                  <th scope="col" className="px-3 py-2 font-semibold">Last visit</th>
                  <th scope="col" className="py-2 pl-3 text-right font-semibold">Owes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {data.items.map((d) => (
                  <tr key={d.id}>
                    <th scope="row" className="py-2.5 pr-3 text-left font-medium">
                      <Link href={`/companies/${d.id}`} className="text-ink hover:underline">
                        {d.name}
                      </Link>
                      {d.city && <span className="block text-meta font-normal text-ink-3">{d.city}</span>}
                    </th>
                    {showOwner && <td className="px-3 py-2.5">{d.owner.name}</td>}
                    <td className="px-3 py-2.5 text-ink-2">{d.lastVisitAt ? fmt.whenLabel(d.lastVisitAt, today) : <span className="text-ink-3">Not yet</span>}</td>
                    <td className="py-2.5 pl-3 text-right tabular-nums">
                      {d.balance ? (
                        <>
                          <span className={d.balance.owedCentavos ? "font-semibold" : "text-ink-3"}>{fmt.peso(d.balance.owedCentavos)}</span>
                          <span className="block text-meta text-ink-3">as of {fmt.dateLabel(d.balance.asOf)}</span>
                        </>
                      ) : (
                        <span className="text-ink-3">No balance</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </>
  );
}
