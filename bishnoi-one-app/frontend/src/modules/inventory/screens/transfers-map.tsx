import { Plus } from "lucide-react";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { PageHeader } from "@/src/modules/inventory/platform/ui/sheet";
import { ToggleLinks } from "@/src/modules/inventory/platform/ui/toggle-links";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { TransferMap, type Shown } from "@/src/modules/inventory/components/transfer-map";
import { NoAccess } from "@/src/modules/inventory/components/ui";
import { context } from "@/src/modules/inventory/lib/page";
import type { MapWarehouse, TransferRoute } from "@/src/modules/inventory/lib/types";

export const metadata = { title: "Transfer map" };

/** A stretch of time, short: "3 d 4 h", "2 h 5 m", "12 m". */
function span(ms: number): string {
  const m = Math.max(0, Math.floor(ms / 60000));
  const d = Math.floor(m / 1440);
  const h = Math.floor((m % 1440) / 60);
  return d ? `${d} d ${h} h` : h ? `${h} h ${m % 60} m` : `${m} m`;
}

// Past these, the clock on a card turns red: a transfer waiting a day for
// approval, or three days on the road, is worth a look.
const WAIT_LATE = 24 * 3600_000;
const ROAD_LATE = 72 * 3600_000;

export default async function TransfersMapPage() {
  const { may, at } = await context();
  if (!may("transfers.view")) return <NoAccess what="transfers" />;
  const { transfersMap: m } = await loadQuery<{ transfersMap: { transfers: TransferRoute[]; warehouses: MapWarehouse[] } }>("query TransfersMap { transfersMap }", {}, ["transfersMap"]);
  const now = Date.now();
  const shown: Shown[] = m.transfers.map((t) => {
    const ago = (iso: string | null) => (iso ? now - new Date(iso).getTime() : 0);
    const step = (iso: string | null, words: string, lateAfter: number, when: string) => ({ ...t, since: span(ago(iso)), sinceLong: `${span(ago(iso))} ${words}`, late: ago(iso) > lateAfter, when });
    if (t.status === "in_transit") return step(t.dispatchedAt, "in transit", ROAD_LATE, `Dispatched ${at(t.dispatchedAt)}`);
    if (t.status === "approved") return step(t.approvedAt, "awaiting dispatch", WAIT_LATE, `Approved ${at(t.approvedAt)}`);
    if (t.status === "requested") return step(t.requestedAt, "pending approval", WAIT_LATE, `Requested ${at(t.requestedAt)}`);
    if (t.status === "received") return { ...t, since: "Received", sinceLong: "received", late: false, when: `Received ${at(t.receivedAt)}` };
    return { ...t, since: "Draft", sinceLong: "not yet requested", late: false, when: `Created ${at(t.createdAt)}` };
  });

  return (
    <>
      <PageHeader
        title="Stock transfers"
        actions={may("transfers.create") && <LinkButton href="/inventory/transfers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New transfer</LinkButton>}
      >
        Open transfers and transfers received in the last 30 days, shown as routes between warehouses.
      </PageHeader>
      <div className="mb-4">
        <ToggleLinks
          current="map"
          options={[
            { value: "list", label: "List", href: "/inventory/transfers" },
            { value: "map", label: "Map", href: "/inventory/transfers/map" },
          ]}
        />
      </div>
      <TransferMap transfers={shown} warehouses={m.warehouses} mayLocate={may("warehouses.manage")} />
    </>
  );
}
