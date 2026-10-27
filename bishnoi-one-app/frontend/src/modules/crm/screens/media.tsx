import Link from "next/link";
import { PageHeader } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CompanyDetail } from "@/src/platform/lib/types";
import type { Material } from "@/src/modules/crm/actions/media";
import { Materials } from "@/src/modules/crm/components/media/materials";

export const metadata = { title: "Documents" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

/** Approved presentations, PDFs and videos to show customers. Opened from a customer's page, each opening counts for them. */
export default async function MediaPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const params = await searchParams;
  const forId = one(params.for);
  const [list, customer] = await Promise.all([
    load<{ items: Material[]; canManage: boolean }>("/media?all=true"),
    forId ? load<CompanyDetail>(`/companies/${encodeURIComponent(forId)}`).catch(() => null) : Promise.resolve(null),
  ]);
  const [products, teams] = list.canManage
    ? await Promise.all([
        load<{ items: { code: string; name: string }[] }>("/products?active=true&limit=500").catch(() => ({ items: [] })),
        load<{ id: string; name: string; isActive: boolean }[]>("/team-names"),
      ])
    : [{ items: [] }, []];
  return (
    <>
      <PageHeader title="Documents" crumbs={customer ? [{ href: `/crm/customers/${customer.id}`, label: customer.name }] : undefined}>
        {customer ? (
          <>
            Approved materials to show <b>{customer.name}</b>. What you open is counted for them.{" "}
            <Link href="/crm/media" className="text-ink underline">
              Not for a customer
            </Link>
          </>
        ) : (
          "Approved presentations, PDFs and videos to show customers. Only what's approved and current for your division is here."
        )}
      </PageHeader>
      <Materials
        items={list.items}
        canManage={list.canManage}
        companyId={customer?.id ?? null}
        products={products.items.map((p) => ({ value: p.code, label: p.name }))}
        teams={teams.filter((t) => t.isActive).map((t) => ({ value: t.id, label: t.name }))}
      />
    </>
  );
}
