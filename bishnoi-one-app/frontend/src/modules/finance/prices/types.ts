// What waits for Finance in the CRM (app/routers/prices.py, from the CRM's /integration/prices).

/** A price a manager set: for the company (kind "product") or one division ("team"). */
export type WaitingPrice = {
  id: string;
  kind: "product" | "team";
  productId: string;
  productCode: string;
  productName: string;
  unit: string;
  teamId: string | null;
  teamName: string;
  priceTypeCode: string;
  priceTypeName: string;
  /** The price in use now; null when there's none yet. */
  currentAmountCentavos: number | null;
  /** 0: the proposal is to take the price away. */
  proposedAmountCentavos: number | null;
  submittedByName: string;
  submittedAt: string | null;
};

/** A quote at a price the rep asked for. */
export type WaitingQuote = {
  id: string;
  number: string;
  customerName: string;
  teamName: string;
  repName: string;
  priceTypeName: string;
  reasons: string[];
  notes: string | null;
  grossCentavos: number;
  totalCentavos: number;
  createdAt: string;
  /** The quote in the CRM, when the CRM says where it is. */
  url: string | null;
  lines: { productCode: string | null; productName: string | null; quantity: number; unitPriceCentavos: number; srpCentavos: number | null; totalCentavos: number }[];
};

export type Waiting = { prices: WaitingPrice[]; quotes: WaitingQuote[]; total: number; canApprove: boolean };
