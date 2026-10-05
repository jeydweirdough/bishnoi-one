import { ADJUSTMENT_STATUSES, COUNT_STATUSES, ORDER_STATUSES, PO_STATUSES, TRANSFER_STATUSES } from "../lib/labels";
import type { AdjustmentBrief, CountStatus, OrderStatus, POStatus, TransferStatus } from "../lib/types";
import { Stamp, type Tone } from "./ui";

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
