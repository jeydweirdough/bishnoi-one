import { PageHeader } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { PriceList } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { QuickQuoteForm } from "../components/quotes/quick-quote-form";
import type { Medicine } from "../components/quotes/medicine-search";

export const metadata = { title: "Quick quote" };

type Params = Promise<{ id: string }>;
type Search = Promise<Record<string, string | string[] | undefined>>;

/**
 * The medicine search for a rep: a customer's medicines at their list price,
 * picked with how many, made into a quote that prints as the quotation letter.
 * Prices a rep types in, or that need a note, are the full quote form's.
 */
export default async function QuickQuotePage({ params, searchParams }: { params: Params; searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "quotes.create")) return <NoAccess what="making quotes" />;
  const { id } = await params;
  const s = await searchParams;
  const [company, list] = await Promise.all([load<{ id: string; name: string }>(`/companies/${enc(id)}`), load<PriceList>(`/companies/${enc(id)}/price-list`)]);
  const types = list.priceTypes.filter((t) => t.entry === "list" && !t.requiresNotes);
  const asked = typeof s.type === "string" ? types.find((t) => t.code === s.type) : undefined;
  const type = asked ?? types.find((t) => !t.needsApproval) ?? types[0];
  const medicines: Medicine[] = type
    ? list.products
        .filter((p) => p.prices[type.code])
        .map((p) => ({ id: p.id, code: p.code, name: p.name, genericName: p.genericName ?? null, strength: p.strength ?? null, form: p.form ?? null, unit: p.unit ?? null, priceCentavos: p.prices[type.code]! }))
    : [];
  return (
    <>
      <PageHeader title="Quick quote" crumbs={[{ href: `/companies/${company.id}`, label: company.name }]}>
        Find the medicines {company.name} needs, at their price, and pick how many: the quote is made, and its quotation letter opens.
      </PageHeader>
      {types.length > 1 && (
        <div className="mb-4">
          <ToggleLinks current={type.code} options={types.map((t) => ({ value: t.code, label: t.name, href: `/companies/${company.id}/quotes/quick?type=${t.code}` }))} />
        </div>
      )}
      {type ? (
        <QuickQuoteForm companyId={company.id} priceType={type.code} medicines={medicines} />
      ) : (
        <p className="text-sm text-ink-3">{company.name} has no list prices yet. Set up their price list under Settings → Pricing, or use New quote.</p>
      )}
    </>
  );
}
