import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { ProductsBulk } from "../components/products-bulk";
import { SelectAllBox, SelectBox, SelectableRow, SelectionProvider } from "@/src/platform/bulk/selection";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Input } from "@/src/platform/ui/field";
import { Flag } from "@/src/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { enc, load } from "@/src/platform/lib/api";
import { departmentModule, may } from "@/src/platform/lib/module";
import { orgFormat } from "@/src/platform/lib/org";
import type { InventoryReference, Product } from "@/src/platform/lib/types";

export const metadata = { title: "Products & prices" };

function describe(p: Product) {
  return [p.code, p.genericName, p.strength, p.form].filter(Boolean).join(" · ");
}

export default async function ProductsPage({ params, searchParams }: { params: Promise<{ module: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module } = await params;
  const search = await searchParams;
  const [mod, fmt] = await Promise.all([departmentModule(module, "inventory"), orgFormat()]);
  const q = typeof search.q === "string" ? search.q.trim() : "";
  const state = search.state === "off" ? "off" : "active";
  const [products, reference] = await Promise.all([
    load<Product[]>(`/inventory/products?state=${state}${q ? `&q=${enc(q)}` : ""}`),
    load<InventoryReference>("/inventory/reference"),
  ]);
  const types = reference.priceTypes.filter((t) => t.isActive);
  const href = (s: string) => `/m/${module}/products?state=${s}${q ? `&q=${enc(q)}` : ""}`;
  const bulk = may(mod, "edit") && products.length > 0;

  return (
    <>
      <PageHeader
        title="Products & prices"
        actions={
          may(mod, "create") && (
            <LinkButton href={`/m/${module}/products/new`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add product
            </LinkButton>
          )
        }
      >
        Prices are per unit. An empty price means the product isn&apos;t sold at it.
      </PageHeader>

      <div className="mb-3 flex flex-wrap items-end gap-3">
        <form className="flex max-w-sm flex-1 items-end gap-2" role="search">
          <input type="hidden" name="state" value={state} />
          <Input name="q" defaultValue={q} placeholder="Name, code or generic name" aria-label="Search products" />
          <Button type="submit" size="sm" icon={<Search className="size-4" aria-hidden />}>
            Search
          </Button>
        </form>
        <ToggleLinks
          current={state}
          options={[
            { value: "active", label: "On sale", href: href("active") },
            { value: "off", label: "Switched off", href: href("off") },
          ]}
        />
      </div>

      <SelectionProvider key={`${state}-${q}`} items={bulk ? products.map((p) => ({ id: p.id, name: p.name })) : []}>
        <Sheet>
          {products.length === 0 ? (
            <Empty icon="products" title={q ? "No products match" : state === "off" ? "Nothing switched off" : "No products yet"}>
              {q ? "Try fewer words." : state === "active" ? "Add the products reps quote, with their prices." : null}
            </Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[48rem] text-left text-sm">
                <thead>
                  <tr className="border-b border-rule text-caps text-ink-3 uppercase">
                    {bulk && (
                      <th scope="col" className="w-12 py-3 pl-5">
                        <SelectAllBox />
                      </th>
                    )}
                    <th scope="col" className={`${bulk ? "pl-2" : "pl-5"} py-3 pr-5 font-semibold`}>Product</th>
                    <th scope="col" className="px-3 py-3 font-semibold">Unit</th>
                    {types.map((t) => (
                      <th key={t.code} scope="col" className="px-3 py-3 text-right font-semibold normal-case tracking-normal">
                        {t.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {products.map((p) => {
                    const missing = types.filter((t) => p.prices[t.code] === undefined).length;
                    return (
                      <SelectableRow key={p.id} id={p.id} className="relative hover:bg-bench/40">
                        {bulk && (
                          <td className="py-3 pl-5 align-top">
                            <SelectBox id={p.id} label={p.name} />
                          </td>
                        )}
                        <td className={`${bulk ? "pl-2" : "pl-5"} py-3 pr-5`}>
                          {/* The name link stretches over the row, so the whole row is the target. */}
                          <Link href={`/m/${module}/products/${p.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                            {p.name}
                          </Link>
                          <span className="block text-meta text-ink-3">{describe(p)}</span>
                          {missing > 0 && p.isActive && (
                            <span className="mt-0.5 block">
                              <Flag letter="!">{missing === 1 ? "1 price missing" : `${missing} prices missing`}</Flag>
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-ink-2">{p.unit}</td>
                        {types.map((t) => (
                          <td key={t.code} className="px-3 py-3 text-right whitespace-nowrap tabular-nums">
                            {p.prices[t.code] !== undefined ? fmt.peso(p.prices[t.code]) : <span className="text-ink-3">—</span>}
                          </td>
                        ))}
                      </SelectableRow>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Sheet>
        {bulk && <ProductsBulk state={state} priceTypes={types.map((t) => ({ code: t.code, name: t.name }))} />}
      </SelectionProvider>
    </>
  );
}
