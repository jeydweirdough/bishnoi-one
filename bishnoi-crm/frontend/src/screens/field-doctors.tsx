import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { NewCustomerButton } from "../components/crm/new-customer";
import { LinkButton } from "@/src/platform/ui/button";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { CoverageCard } from "../components/field/coverage";
import { PlanPicker } from "../components/field/plan";
import { ZONES } from "../components/field/words";
import { Pager } from "@/src/platform/ui/pager";
import { pageOf, slicePage } from "@/src/platform/ui/paging";
import { LogVisitButton } from "../components/field/log-visit";
import type { Coverage, Doctors } from "../components/field/types";
import { isFieldAgent } from "../components/field/words";
import { counted, lower, termsOf } from "../components/terms/terms";

export const metadata = { title: "Field accounts" };

/** The accounts someone visits (the company's word: doctors at GetMeds), most owed first: what each owes and when they were last seen. */
export default async function FieldDoctorsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  const terms = termsOf(me);
  const one = lower(terms.visited.one);
  if (!can(me, "visits.view")) return <NoAccess what={`${one} balances`} />;
  const { q, owed, page, zone: z, tier: t, sort: o } = await searchParams;
  const search = typeof q === "string" ? q : "";
  const onlyOwed = owed === "1";
  const zone = ["red", "yellow", "green", "none"].includes(String(z)) ? String(z) : "";
  const tier = ["1", "2", "3"].includes(String(t)) ? String(t) : "";
  // By the plan (zone, then tier) unless asked for who owes most.
  const sort = o === "owed" ? "owed" : "plan";
  const query = new URLSearchParams({ limit: "500", sort, ...(search && { search }), ...(onlyOwed && { owed: "true" }), ...(zone && { zone }), ...(tier && { tier }) });
  const [data, coverage] = await Promise.all([load<Doctors>(`/field/doctors?${query}`), load<Coverage>("/field/coverage")]);
  const fmt = makeFormat(me.org);
  const today = fmt.todayKey();
  const showOwner = me.role?.scope !== "own";
  const plans = can(me, "visits.create");
  // All of them are in hand (the visit picker needs every name), so a page is a slice.
  const shown = slicePage(data.items, pageOf(page));
  const keep = { ...(search && { q: search }), ...(onlyOwed && { owed: "1" }), ...(zone && { zone }), ...(tier && { tier }), ...(sort === "owed" && { sort }) };
  const here = new URLSearchParams(keep);
  const link = (change: Record<string, string>) => {
    const next = new URLSearchParams({ ...keep, ...change });
    for (const [k, v] of [...next.entries()]) if (!v) next.delete(k);
    return `/field/doctors${next.size ? `?${next}` : ""}`;
  };

  return (
    <>
      <PageHeader
        title={terms.visited.many}
        actions={
          can(me, "visits.create") && (
            <LogVisitButton requireLocation={isFieldAgent(me)} variant="primary" org={me.org} now={new Date().toISOString()} doctors={data.items.map((d) => ({ id: d.id, name: d.name, pin: d.pin, zone: d.zone }))} />
          )
        }
      >
        {counted(data.total, terms)} · {fmt.peso(data.owedCentavos)} total outstanding
      </PageHeader>

      <form className="mb-4 flex flex-wrap items-center gap-3" action="/field/doctors">
        <input
          name="q"
          defaultValue={search}
          placeholder="Search by name"
          aria-label={`Search ${lower(terms.visited.many)} by name`}
          className="h-9 w-64 rounded-lg border border-rule-strong bg-sheet px-3 text-sm hover:border-control focus:border-hema focus:outline-none"
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="owed" value="1" defaultChecked={onlyOwed} className="size-4 accent-hema" />
          With outstanding balance
        </label>
        {zone && <input type="hidden" name="zone" value={zone} />}
        {tier && <input type="hidden" name="tier" value={tier} />}
        {sort === "owed" && <input type="hidden" name="sort" value="owed" />}
        <button type="submit" className="h-9 rounded-lg border border-rule-strong bg-sheet px-4 text-sm font-semibold hover:border-control">
          Show
        </button>
      </form>
      {/* The plan's filters: a zone, a tier, and the order. */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <ToggleLinks
          current={zone}
          options={[{ value: "", label: "All zones", href: link({ zone: "" }) }, ...ZONES.map((x) => ({ value: x.value, label: x.label, href: link({ zone: x.value }) })), { value: "none", label: "No zone", href: link({ zone: "none" }) }]}
        />
        <ToggleLinks
          current={tier}
          options={[{ value: "", label: "All tiers", href: link({ tier: "" }) }, ...(["1", "2", "3"] as const).map((x) => ({ value: x, label: `Tier ${x}`, href: link({ tier: x }) }))]}
        />
        <span className="ml-auto">
          <ToggleLinks
            current={sort}
            options={[
              { value: "plan", label: "By plan", href: link({ sort: "" }) },
              { value: "owed", label: "Highest balance", href: link({ sort: "owed" }) },
            ]}
          />
        </span>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_19rem] xl:items-start">
      {/* The month against the plan: first on a phone, beside the list on a wide screen. */}
      <div className="xl:order-2">
        <CoverageCard coverage={coverage} monthName={`${fmt.monthLabel(coverage.month)} ${coverage.month.slice(0, 4)}`} many={lower(terms.visited.many)} />
      </div>
      <div className="min-w-0">
      <Sheet className="px-5 pt-2 pb-3">
        {data.items.length === 0 ? (
          <Empty
            title={`No ${lower(terms.visited.many)} here`}
            icon="customers"
            actions={
              search || onlyOwed ? (
                <LinkButton href="/field/doctors">Clear search</LinkButton>
              ) : (
                <>
                  {can(me, "customers.create") && (
<NewCustomerButton label={`Add a ${one}`} kind={terms.visitedType ?? undefined} icon={false} />
                  )}
                  {can(me, "goals.import") && <LinkButton href="/field/balances/import">Upload balances</LinkButton>}
                </>
              )
            }
          >
            {search || onlyOwed ? "No matching records. Clear the search to see all." : `${terms.visited.many} are the customers you visit, given to you by your lead or the admin.`}
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th scope="col" className="py-2 pr-3 font-semibold">{terms.visited.one}</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Plan</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">This month</th>
                  {showOwner && <th scope="col" className="px-3 py-2 font-semibold">Visited by</th>}
                  <th scope="col" className="px-3 py-2 font-semibold">Last visit</th>
                  <th scope="col" className="py-2 pl-3 text-right font-semibold">Outstanding</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {shown.rows.map((d) => (
                  <tr key={d.id}>
                    <th scope="row" className="py-2.5 pr-3 text-left font-medium">
                      <Link href={`/companies/${d.id}`} className="text-ink hover:underline">
                        {d.name}
                      </Link>
                      {(d.city || d.careGroupAt) && (
                        <span className="block text-meta font-normal text-ink-3">
                          {d.city}
                          {d.city && d.careGroupAt && " · "}
                          {d.careGroupAt && <span className="text-filed">In a Patient Care Group</span>}
                        </span>
                      )}
                    </th>
                    <td className="px-3 py-2.5">
                      <PlanPicker id={d.id} name={d.name} plan={{ tier: d.tier, zone: d.zone }} editable={plans} />
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums" title={d.visitsNeeded ? `${d.visitsNeeded} a month for tier ${d.tier}` : undefined}>
                      <span className={d.visitsNeeded && d.visitsThisMonth >= d.visitsNeeded ? "font-semibold text-filed" : "text-ink"}>{d.visitsThisMonth}</span>
                      {d.visitsNeeded && <span className="text-ink-3"> of {d.visitsNeeded}</span>}
                    </td>
                    {showOwner && <td className="px-3 py-2.5">{d.owner.name}</td>}
                    <td className="px-3 py-2.5 text-ink-2">{d.lastVisitAt ? fmt.whenLabel(d.lastVisitAt, today) : <span className="text-ink-3">Never</span>}</td>
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
      <Pager total={data.items.length} page={shown.page} base={`/field/doctors${here.size ? `?${here}` : ""}`} />
      </div>
      </div>
    </>
  );
}
