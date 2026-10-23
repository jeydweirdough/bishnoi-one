import { Clock, FilePen, PackageCheck, PackageOpen, PackageX, Truck } from "lucide-react";
import { ADJUSTMENT_STATUSES, COUNT_STATUSES, ORDER_STATUSES, PO_STATUSES, TRANSFER_STATUSES } from "@/src/modules/inventory/lib/labels";
import type { AdjustmentBrief, CountStatus, OrderStatus, POStatus, TransferStatus } from "@/src/modules/inventory/lib/types";
import { Stamp, type Tone } from "@/src/modules/inventory/components/ui";

// Each document's status, stamped the same way everywhere: waiting on someone
// is dashed, under way is tinted, finished is solid, and cancelled is faded.

const PO: Record<POStatus, Tone> = { draft: "neutral", ordered: "active", partial: "active", received: "done", cancelled: "muted" };
const ORDER: Record<OrderStatus, Tone> = { draft: "neutral", confirmed: "active", picking: "active", issued: "done", cancelled: "muted" };
const TRANSFER: Record<TransferStatus, Tone> = { draft: "neutral", requested: "neutral", approved: "active", in_transit: "active", received: "done", cancelled: "muted" };
const ADJUSTMENT: Record<AdjustmentBrief["status"], Tone> = { pending: "neutral", posted: "done", rejected: "muted" };
const COUNT: Record<CountStatus, Tone> = { open: "active", submitted: "neutral", approved: "done", cancelled: "muted" };

export function POStamp({ status, late }: { status: POStatus; late?: boolean }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      <Stamp tone={PO[status]}>{PO_STATUSES[status]}</Stamp>
      {late && <Stamp tone="attention">Late</Stamp>}
    </span>
  );
}
export const OrderStamp = ({ status }: { status: OrderStatus }) => <Stamp tone={ORDER[status]}>{ORDER_STATUSES[status]}</Stamp>;
export const TransferStamp = ({ status }: { status: TransferStatus }) => <Stamp tone={TRANSFER[status]}>{TRANSFER_STATUSES[status]}</Stamp>;
export const AdjustmentStamp = ({ status }: { status: AdjustmentBrief["status"] }) => <Stamp tone={ADJUSTMENT[status]}>{ADJUSTMENT_STATUSES[status]}</Stamp>;
export const CountStamp = ({ status }: { status: CountStatus }) => <Stamp tone={COUNT[status]}>{COUNT_STATUSES[status]}</Stamp>;

/** A purchase order's status as a small icon (beside a name, where a stamp is too much), its words on hover and for screen readers. */
export function POStatusIcon({ status, late }: { status: POStatus; late?: boolean }) {
  const icon = {
    draft: { Of: FilePen, color: "text-ink-3" },
    ordered: { Of: Truck, color: "text-[#2a78d6]" },
    partial: { Of: PackageOpen, color: "text-[#8a5a00]" },
    received: { Of: PackageCheck, color: "text-filed" },
    cancelled: { Of: PackageX, color: "text-danger" },
  }[status];
  const said = `${PO_STATUSES[status]}${late ? ", late" : ""}`;
  // Recognition over recall: the common states (received, ordered) read from the
  // icon alone; the rarer ones, and a late order, say it in a word too.
  const word = late ? "Late" : status === "partial" ? "Partial" : status === "cancelled" ? "Cancelled" : status === "draft" ? "Draft" : null;
  return (
    <span title={said} className={`inline-flex shrink-0 items-center gap-1 ${late ? "text-danger" : icon.color}`}>
      <icon.Of className="size-4" aria-hidden />
      {late && <Clock className="size-3.5" aria-hidden />}
      {word ? <span className="text-meta font-medium" aria-hidden>{word}</span> : null}
      <span className="sr-only">{said}</span>
    </span>
  );
}
