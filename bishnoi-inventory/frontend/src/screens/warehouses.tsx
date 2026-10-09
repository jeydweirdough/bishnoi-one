import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { deleteWarehouse } from "../actions/inventory";
import { RecordTools } from "../components/record-tools";
import { Figures, NoAccess, RowLink, Table, Td } from "../components/ui";
import { AddWarehouse, EditWarehouse, LocationsEditor } from "../components/warehouse-forms";
import { context, type Params } from "../lib/page";
import type { Warehouse, WarehouseRow } from "../lib/types";

export async function WarehousesPage() {
  const { fmt, may } = await context();
  if (!may("warehouses.view")) return <NoAccess what="warehouses" />;
  const { warehouses } = await loadQuery<{ warehouses: WarehouseRow[] }>("query Warehouses { warehouses }", {}, ["warehouses"]);
  return (
    <>
      <PageHeader title="Warehouses">Every place stock is kept. Each has its own stock, and locations (zones, racks, bins) inside it.</PageHeader>
      {may("warehouses.manage") && <div className="mb-5"><AddWarehouse /></div>}
      <Sheet>
        {warehouses.length === 0 ? (
          <Empty icon="warehouses" title="No warehouses yet">Add one, then receive stock into it.</Empty>
        ) : (
          <Table head={["Warehouse", "Address", " Locations", " Products", " Units", " Value"]}>
            {warehouses.map((w) => (
              <tr key={w.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/warehouses/${w.id}`} sub={w.isActive ? w.code : `${w.code} · switched off`}>{w.name}</RowLink></Td>
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
          crumbs={[{ href: "/warehouses", label: "Warehouses" }]}
          title={w.name}
          tools={
            manage && (
              <>
                <EditWarehouse warehouse={w} />
                <RecordTools what="warehouse" name={w.name} remove={deleteWarehouse.bind(null, w.id)} after="/warehouses" removeNote="Only a warehouse stock has never moved through can be deleted. Otherwise, switch it off." />
              </>
            )
          }
          actions={
            <>
              {may("stock.view") && <LinkButton href={`/stock?warehouse=${w.id}`}>Its stock</LinkButton>}
              {may("counts.create") && <LinkButton href={`/counts?warehouse=${w.id}`}>Count it</LinkButton>}
            </>
          }
        >
          <span className="font-mono text-meta">{w.code}</span>
          {w.address && <> · {w.address}</>}
          {!w.isActive && <> · <strong>Switched off</strong></>}
        </PageHeader>
      </div>
      <Figures
        items={[
          { label: "Units on hand", value: fmt.count(s.onHand), href: `/stock?warehouse=${w.id}` },
          { label: "Available", value: fmt.count(s.available) },
          { label: "Held for orders", value: fmt.count(s.reserved + s.allocated) },
          { label: "Coming in", value: fmt.count(s.inTransit) },
          { label: "Value at cost", value: fmt.peso(w.value) },
          { label: "Low or out here", value: fmt.count(w.lowCount), flag: w.lowCount > 0, href: `/stock?warehouse=${w.id}&state=low` },
        ]}
      />
      <Sheet className="mt-5 max-w-3xl">
        <div className="px-5 pt-4 pb-2">
          <SectionTitle icon="headquarters">Locations</SectionTitle>
          <p className="text-meta text-ink-3">Stock received or moved here goes to the default location unless someone picks another.</p>
        </div>
        <LocationsEditor warehouseId={w.id} locations={w.locations} canManage={manage} />
      </Sheet>
    </>
  );
}
