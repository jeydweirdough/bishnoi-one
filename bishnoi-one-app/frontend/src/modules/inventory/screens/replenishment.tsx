import Link from "next/link";
import { load } from "@/src/modules/inventory/platform/lib/api";
import { NoAccess, Table, Td } from "@/src/modules/inventory/components/ui";
import { MakeDrafts, ReplenishmentSettingsForm } from "@/src/modules/inventory/components/replenishment";
import { context, type Search } from "@/src/modules/inventory/lib/page";
import { referenceOf } from "@/src/modules/inventory/lib/reference";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import type { Reference, ReplenishmentRow, ReplenishmentSettings } from "@/src/modules/inventory/lib/types";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";

// Replenishment (feature plan step 15a): what to order now, from use and lead time, and the drafts it makes.

const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export async function ReplenishmentPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may } = await context();
  if (!may("purchasing.view")) return <NoAccess what="replenishment" />;
  const s = await searchParams;
  const all = one(s.all) === "1";
  const chosen = one(s.warehouse);
  const [data, { reference }] = await Promise.all([
    load<{ warehouse: { id: string; name: string } | null; rows: ReplenishmentRow[]; settings: ReplenishmentSettings; due: number; needVendor: number }>(
      `/inventory/replenishment?${new URLSearchParams({ ...(chosen && { warehouse: chosen }), ...(all && { all: "true" }) })}`,
    ),
    loadQuery<{ reference: Pick<Reference, "warehouses"> }>(`query W { ${referenceOf("warehouses")} }`, {}, ["reference"]),
  ]);
  const w = data.warehouse;
  const here = (extra: Record<string, string>) => `/inventory/replenishment?${new URLSearchParams({ ...(w && { warehouse: w.id }), ...extra })}`;
  return (
    <>
      <PageHeader
        title="Replenishment"
        tools={
          <ToggleLinks
            current={w?.id ?? ""}
            options={reference.warehouses.filter((x) => x.isActive).map((x) => ({ value: x.id, label: x.name, href: `/inventory/replenishment?warehouse=${x.id}${all ? "&all=1" : ""}` }))}
          />
        }
        actions={w && may("purchasing.create") && <MakeDrafts warehouseId={w.id} due={data.due ?? 0} />}
      >
        What to order now, worked out from each item&apos;s use over the last {data.settings.historyDays} days, its vendor&apos;s lead time plus {data.settings.safetyDays} safety days, and what is already on order.
      </PageHeader>
      <div className="mb-3 flex flex-wrap gap-3 text-sm">
        <Link href={here({})} className={!all ? "font-semibold text-ink" : "text-hema hover:underline"}>Due now ({data.due ?? 0})</Link>
        <Link href={here({ all: "1" })} className={all ? "font-semibold text-ink" : "text-hema hover:underline"}>Every item</Link>
        {(data.needVendor ?? 0) > 0 && <span className="text-danger">{data.needVendor} due without a usual vendor: set one on the item.</span>}
      </div>
      <Sheet className="mb-5">
        {data.rows.length === 0 ? (
          <Empty icon="reorder" title={all ? "No stocked items" : "Nothing to order now"} source="Items' reorder points, minimums and maximums, their use (issues), and vendor lead times." />
        ) : (
          <Table head={["Item", "Vendor", " Available", " On order", " Use a day", " Lead days", " Order point", " Days left", " Order"]} min="60rem">
            {data.rows.map((r) => (
              <tr key={r.product.id} className="relative hover:bg-bench/40">
                <Td><Link href={`/inventory/products/${r.product.id}`} className="font-medium text-ink hover:underline">{r.product.name}</Link><span className="block text-meta text-ink-3">{r.product.sku}</span></Td>
                <Td>{r.supplier?.name ?? <span className="text-danger">None set</span>}</Td>
                <Td num>{fmt.count(r.available)}</Td>
                <Td num>{fmt.count(r.onOrder + r.inTransit)}</Td>
                <Td num>{r.dailyUse}</Td>
                <Td num>{r.leadDays} + {r.safetyDays}</Td>
                <Td num>{fmt.count(r.orderPoint)}</Td>
                <Td num className={r.daysLeft !== null && r.daysLeft <= r.leadDays + r.safetyDays ? "font-semibold text-danger" : undefined}>{r.daysLeft ?? "—"}</Td>
                <Td num className="font-semibold">{r.suggested ? fmt.count(r.suggested) : "—"}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
      <Sheet className="px-5 py-4">
        <ReplenishmentSettingsForm settings={data.settings} canChange={may("purchasing.approve")} />
      </Sheet>
    </>
  );
}
