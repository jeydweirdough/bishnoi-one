export type PurchaseAllocationInput = { intakeId: string; sourceLineId: string; version: number; quantity: number };
export type PurchaseSource = { supplierId: string; currency: string; rows: (PurchaseAllocationInput & { label: string; unit: string; maximum: number; unitCost: number })[] };
export type PurchaseIntake = {
  id: string; version: number; state: string; holds: string[]; remaining: number;sourceConflict:boolean;
  supplier: { id: string; name: string } | null;
  snapshot: { receiptId: string; receiptNumber: string; orderId: string; orderNumber: string; supplierName: string; currencyEvidence: string; deliveryRef: string | null };
  lines: { id: string; product: string; unit: string; quantity: number; unitCost: number; allocated: number; remaining: number }[];
  bills: { id: string; number: string; state: string }[];
};
export type PurchaseQueue = { items: PurchaseIntake[]; total:number;limit:number;offset:number;canPrepare: boolean; canLinkSupplier: boolean };
export const PURCHASE_STATES: Record<string,string> = { received: 'Waiting for Finance', held: 'Needs Finance review', needs_correction: 'Waiting for receiving correction', partially_allocated: 'Partly prepared', allocated: 'Bill prepared' };
