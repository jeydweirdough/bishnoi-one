import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { Flag } from "@/src/modules/pharmacy/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { ToggleLinks } from "@/src/modules/pharmacy/platform/ui/toggle-links";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { Head, MedicineStatusMark, NoAccess, Qty, RxClassMark, SearchBar, Tabs } from "@/src/modules/pharmacy/components/bits";
import { NamedList } from "@/src/modules/pharmacy/components/named-list";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import type { Brand, Category, Medicine } from "@/src/modules/pharmacy/lib/types";

export const metadata = { title: "Medicines" };

const STATES = ["active", "inactive", "discontinued", "all"] as const;
const STATE_LABELS = { active: "Active", inactive: "Inactive", discontinued: "Discontinued", all: "All" };

export default async function MedicinesPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("medicines.view");
  if (!allowed) return <NoAccess what="medicines" />;
  const search = await searchParams;
  const tab = ["categories", "brands"].includes(param(search, "tab")) ? param(search, "tab") : "catalog";
  const q = param(search, "q");
  const state = (STATES as readonly string[]).includes(param(search, "state")) ? param(search, "state") : "active";
  const category = param(search, "category");
  // The medicines on sale with no price: the sidebar's red count on Medicines.
  const missing = param(search, "missing") === "1";

  const tabs = (
    <Tabs
      label="Medicines"
      current={tab}
      tabs={[
        { value: "catalog", label: "Medicine catalog", href: "/pharmacy/medicines" },
        { value: "categories", label: "Categories", href: "/pharmacy/medicines?tab=categories" },
        { value: "brands", label: "Brands", href: "/pharmacy/medicines?tab=brands" },
      ]}
    />
  );

  if (tab !== "catalog") {
    const rows =
      tab === "brands"
        ? (await load<Brand[]>("/medicines/brands")).map((b) => ({ ...b, extra: b.manufacturer }))
        : (await load<Category[]>("/medicines/categories")).map((c) => ({ ...c, extra: c.description }));
    return (
      <>
        <PageHeader title="Medicines">{tab === "brands" ? "The brands medicines are sold under, and who makes them." : "How the catalogue is grouped."}</PageHeader>
        {tabs}
        <Sheet>
          <NamedList kind={tab === "brands" ? "brand" : "category"} rows={rows} canCreate={may("medicines.create")} canEdit={may("medicines.edit")} canDelete={may("medicines.delete")} />
        </Sheet>
      </>
    );
  }

  const [medicines, categories] = await Promise.all([
    load<Medicine[]>(`/medicines?state=${state}${q ? `&q=${enc(q)}` : ""}${category ? `&categoryId=${enc(category)}` : ""}${missing ? "&missing=true" : ""}`),
    load<Category[]>("/medicines/categories"),
  ]);
  const href = (s: string) => `/pharmacy/medicines?state=${s}${q ? `&q=${enc(q)}` : ""}${category ? `&category=${enc(category)}` : ""}`;
  const inCategory = categories.find((c) => c.id === category);
  const unpriced = medicines.filter((m) => m.priceCentavos === 0).length;

  return (
    <>
      <PageHeader
        title="Medicines"
        actions={
          may("medicines.create") && (
            <LinkButton href="/pharmacy/medicines/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add medicine
            </LinkButton>
          )
        }
      >
        Prices are per unit. Available counts only what can be given out today: not expired, not held back.
        {missing ? (
          <span className="mt-1 block text-danger">
            Showing the medicines on sale with no price. A sale is priced from here, so they would sell for nothing.{" "}
            <Link href="/pharmacy/medicines" className="font-semibold underline">
              Show every medicine
            </Link>
          </span>
        ) : (
          state === "active" &&
          unpriced > 0 && (
            <span className="mt-1 block text-danger">
              {unpriced} {unpriced === 1 ? "medicine has" : "medicines have"} no price, so {unpriced === 1 ? "it" : "they"} would sell for nothing.{" "}
              <Link href="/pharmacy/medicines?missing=1" className="font-semibold underline">
                Show {unpriced === 1 ? "it" : "them"}
              </Link>
            </span>
          )
        )}
      </PageHeader>
      {tabs}
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <SearchBar q={q} placeholder="Name, code or brand" keep={{ state, ...(category ? { category } : {}) }} />
        <ToggleLinks current={state} options={STATES.map((s) => ({ value: s, label: STATE_LABELS[s], href: href(s) }))} />
      </div>
      {categories.length > 0 && (
        <nav aria-label="Categories" className="mb-3 flex flex-wrap gap-1.5">
          {[{ id: "", name: "Every category" }, ...categories.filter((c) => c.isActive)].map((c) => (
            <Link
              key={c.id}
              href={`/pharmacy/medicines?state=${state}${q ? `&q=${enc(q)}` : ""}${c.id ? `&category=${c.id}` : ""}`}
              aria-current={c.id === category ? "true" : undefined}
              className={`rounded-full border px-2.5 py-0.5 text-meta ${c.id === category ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong text-ink-2 hover:text-ink"}`}
            >
              {c.name}
            </Link>
          ))}
        </nav>
      )}

      <Sheet>
        {medicines.length === 0 ? (
          <Empty icon="medicines" title={q || inCategory ? "No medicines match" : state === "active" ? "No medicines yet" : `Nothing ${STATE_LABELS[state as "active"].toLowerCase()}`}>
            {!q && state === "active" && !inCategory ? "Add the medicines the pharmacy stocks." : null}
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <Head columns={["Medicine", "Category", "Class", { label: "Price", right: true }, { label: "On hand", right: true }, { label: "Available", right: true }]} />
              <tbody className="divide-y divide-rule">
                {medicines.map((m) => (
                  <tr key={m.id} className="relative hover:bg-bench/40">
                    <td className="py-3 pr-3 pl-5">
                      <span className="flex flex-wrap items-center gap-2">
                        <Link href={`/pharmacy/medicines/${m.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                          {m.label}
                        </Link>
                        <MedicineStatusMark status={m.status} />
                      </span>
                      <span className="block text-meta text-ink-3">
                        {m.code} · per {m.unit}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-ink-2">{m.category?.name ?? "—"}</td>
                    <td className="px-3 py-3">
                      <RxClassMark rxClass={m.rxClass} />
                    </td>
                    <td className="px-3 py-3 text-right whitespace-nowrap tabular-nums">{fmt.peso(m.priceCentavos)}</td>
                    <td className="px-3 py-3 text-right">
                      <Qty n={m.onHand ?? 0} />
                    </td>
                    <td className="py-3 pr-5 pl-3 text-right">
                      {m.status === "active" && (m.available ?? 0) <= m.reorderLevel ? <Flag letter="!">{m.available ?? 0}</Flag> : <Qty n={m.available ?? 0} />}
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
