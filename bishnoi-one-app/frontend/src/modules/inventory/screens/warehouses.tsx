import Link from "next/link";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { deleteWarehouse } from "@/src/modules/inventory/actions/inventory";
import { RecordTools } from "@/src/modules/inventory/components/record-tools";
import { Figures, NoAccess, RowLink, Stamp, Table, Td } from "@/src/modules/inventory/components/ui";
import { BarList, Card, DetailPanel, InfoCard, InfoSection, StatCards } from "@/src/modules/inventory/components/detail";
import { Icon } from "@/src/modules/inventory/platform/ui/icons";
import { AddWarehouse, EditWarehouse, LocationsEditor } from "@/src/modules/inventory/components/warehouse-forms";
import { context, type Params, type Search } from "@/src/modules/inventory/lib/page";
import type { Warehouse, WarehouseRow } from "@/src/modules/inventory/lib/types";

export async function WarehousesPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may } = await context();
  if (!may("warehouses.view")) return <NoAccess what="warehouses" />;
  const { warehouses } = await loadQuery<{ warehouses: WarehouseRow[] }>("query Warehouses { warehouses }", {}, ["warehouses"]);
  return (
    <>
      <PageHeader title="Warehouses">All sites where stock is kept. Each warehouse has its own stock and locations (zones, racks and bins).</PageHeader>
      {may("warehouses.manage") && <div className="mb-5"><AddWarehouse startOpen={(await searchParams).add === "1" || warehouses.length === 0} /></div>}
      <Sheet>
        {warehouses.length === 0 ? (
          <Empty icon="warehouses" title="No warehouses">Add a warehouse, then receive stock into it.</Empty>
        ) : (
          <Table head={["Warehouse", "Address", " Locations", " Products", " Units", " Value"]}>
            {warehouses.map((w) => (
              <tr key={w.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/inventory/warehouses/${w.id}`} sub={w.isActive ? w.code : `${w.code} · inactive`}>{w.name}</RowLink></Td>
                <Td className="text-ink-2">{w.address ?? "—"}</Td>
                <Td num>{w.locationCount}</Td>
                <Td num>{fmt.count(w.products)}</Td>
                <Td num>{fmt.count(w.units)}</Td>
                <Td num>{fmt.peso(w.value)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function WarehousePage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may } = await context();
  if (!may("warehouses.view")) return <NoAccess what="warehouses" />;
  const { warehouse: w } = await loadQuery<{ warehouse: Warehouse }>(`query Warehouse($id: String!) { warehouse(id: $id) }`, { id }, ["warehouse"]);
  const s = w.summary;
  const manage = may("warehouses.manage");
  return (
    <>
      <div className="relative">
        <PageHeader
          crumbs={[{ href: "/inventory/warehouses", label: "Warehouses" }]}
          title={w.name}
          tools={
            manage && (
              <>
                <EditWarehouse warehouse={w} />
                <RecordTools what="warehouse" name={w.name} remove={deleteWarehouse.bind(null, w.id)} after="/inventory/warehouses" removeNote="Only a warehouse with no stock movements can be deleted. Otherwise, deactivate it." />
              </>
            )
          }
          actions={
            <>
              {may("stock.view") && <LinkButton href={`/inventory/stock?warehouse=${w.id}`}>View stock</LinkButton>}
              {may("counts.create") && <LinkButton href={`/inventory/counts?warehouse=${w.id}`}>Start count</LinkButton>}
            </>
          }
        >
          <span className="font-mono text-meta">{w.code}</span>
          {w.address && <> · {w.address}</>}
          {!w.isActive && <> · <strong>Inactive</strong></>}
        </PageHeader>
      </div>
      <DetailPanel>
        <StatCards
          items={[
            { label: "Units on hand", value: fmt.count(s.onHand), href: `/inventory/stock?warehouse=${w.id}`, note: s.inTransit ? `${fmt.count(s.inTransit)} in transit` : undefined },
            { label: "Available", value: fmt.count(s.available), note: s.reserved + s.allocated ? `${fmt.count(s.reserved + s.allocated)} reserved for orders` : undefined },
            { label: "Low or out of stock", value: fmt.count(w.lowCount), flag: w.lowCount > 0, href: `/inventory/stock?warehouse=${w.id}&state=low` },
          ]}
        />
        <InfoCard>
          <InfoSection
            icon="info"
            title="Basic information"
            items={[
              ["Warehouse name", w.name],
              ["Code", <span key="code" className="font-mono">{w.code}</span>],
              ["Address", w.address],
              ["Status", w.isActive ? "Active" : "Inactive"],
              ["Default location", w.locations.find((l) => l.isDefault)?.name],
              ["Locations", fmt.count(w.locations.filter((l) => l.isActive).length)],
            ]}
          />
          <InfoSection
            icon="stock"
            title="Inventory"
            action={may("stock.view") && <Link href={`/inventory/movements?warehouse=${w.id}`} className="inline-flex items-center gap-1.5 text-meta text-ink hover:underline"><Icon name="history" className="size-3.5" />Movement history</Link>}
            items={[
              ["On hand", fmt.count(s.onHand)],
              ["Value at cost", fmt.peso(w.value)],
              ["Reserved", fmt.count(s.reserved)],
              ["Allocated", fmt.count(s.allocated)],
              ["Damaged", fmt.count(s.damaged)],
              ["In transit", fmt.count(s.inTransit)],
            ]}
          />
        </InfoCard>
        {!manage && (
        <BarList
          title="Stock by location"
          icon="headquarters"
          rows={w.locations.map((l) => ({
            key: l.id,
            name: `${l.code} · ${l.name}`,
            sub: `${fmt.count(l.units)} units · ${fmt.count(l.products)} ${l.products === 1 ? "product" : "products"}`,
            pill: !l.isActive ? <Stamp tone="muted">Inactive</Stamp> : l.isDefault ? <Stamp tone="active">Default</Stamp> : null,
            share: l.units / Math.max(1, s.onHand),
          }))}
          empty="No locations."
        />
        )}
        {manage && (
          <Card>
            <div className="px-5 pt-4 pb-2">
              <SectionTitle icon="headquarters">Locations</SectionTitle>
              <p className="text-meta text-ink-3">Stock received or transferred here goes to the default location unless another is selected.</p>
            </div>
            <LocationsEditor warehouseId={w.id} locations={w.locations} canManage={manage} />
          </Card>
        )}
      </DetailPanel>
    </>
  );
}
