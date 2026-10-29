import type { DocumentHeader } from "@/src/platform/ui/document-header";
// What Inventory's API sends, as the screens read it. Money is in minor units
// (centavos); quantities are whole units of the product's unit of measure.

export type Ref = { id: string; code: string; name: string };
export type Person = { id: string; name: string } | null;

export type ProductRef = {
  id: string;
  sku: string;
  name: string;
  unit: string;
  trackBatches: boolean;
  trackExpiry: boolean;
  trackSerials: boolean;
};

export type Expiry = "expired" | "expiring" | "ok" | null;

export type BatchRef = {
  id: string;
  batchNo: string;
  manufacturedOn: string | null;
  expiresOn: string | null;
  expiry: Expiry;
  receivedAt: string;
};

/** Every quantity of a product, overall or in one warehouse. */
export type Level = {
  onHand: number;
  damaged: number;
  /** Received and waiting for its quality check (step 14a): on hand, not usable yet. */
  onHold?: number;
  reserved: number;
  allocated: number;
  available: number;
  inTransit: number;
};

export type StockState = "out" | "low" | "over" | "ok" | null;

export type Reference = {
  categories: { id: string; name: string; path: string; parentId: string | null; isActive: boolean }[];
  brands: { id: string; name: string; isActive: boolean }[];
  units: { code: string; name: string; isActive: boolean }[];
  suppliers: (Ref & { isActive: boolean })[];
  warehouses: (Ref & { isActive: boolean; locations: { id: string; code: string; name: string; isDefault: boolean; isActive: boolean }[] })[];
  products: (ProductRef & { status: ProductStatus; costPrice: number; sellingPrice: number; supplierId: string | null; packagings?: { name: string; quantity: number }[] })[];
};

export type ProductType = "stock" | "consumable" | "asset" | "service";
export type ProductStatus = "active" | "inactive" | "discontinued";

export type CprState = "missing" | "no_date" | "expired" | "expiring" | "valid" | "not_needed";
/** A product's FDA Certificate of Product Registration and where it stands (Inventory app/cpr.py). */
export type Cpr = { number: string | null; validUntil: string | null; daysLeft: number | null; state: CprState; label: string };

export type ProductRow = ProductRef & {
  barcode: string | null;
  category: { id: string; name: string; path: string } | null;
  brand: { id: string; name: string } | null;
  supplier: Ref | null;
  productType: ProductType;
  status: ProductStatus;
  costPrice: number;
  sellingPrice: number;
  reorderPoint: number;
  minStock: number;
  maxStock: number | null;
  parentId: string | null;
  variantLabel: string | null;
  variantCount: number;
  level: Level;
  state: StockState;
  value: number;
  cpr: Cpr;
};

export type MovementBrief = {
  id: number;
  at: string;
  kind: MovementKind;
  quantity: number;
  warehouse: Ref;
  batchNo: string | null;
  reference: string | null;
  referenceType: string | null;
  referenceId: string | null;
  user: string;
};

export type Product = ProductRow & {
  /** Vendors' consignment stock in it (15d): on hand, not ours, not in its value. */
  consigned?: number;
  /** Its packs (step 14e); stock stays in its base unit. */
  packagings?: PackagingRow[];
  description: string | null;
  unitName: string;
  taxRateBp: number;
  taxInclusive: boolean;
  reorderQty: number;
  suggestedOrder: number;
  attributes: Record<string, string>;
  parent: { id: string; sku: string; name: string } | null;
  createdAt: string;
  updatedAt: string;
  warehouses: (Level & { warehouse: Ref })[];
  balances: { warehouse: Ref; location: { id: string; code: string; name: string }; batch: BatchRef | null; onHand: number; damaged: number }[];
  batches: (BatchRef & { onHand: number })[];
  variants: ProductRow[];
  supplierPrices: { supplier: Ref; supplierSku: string | null; price: number; leadTimeDays: number | null; updatedAt: string }[];
  images: string[];
  recentMovements: MovementBrief[];
};

export type CategoryRow = {
  id: string;
  name: string;
  path: string;
  parentId: string | null;
  description: string | null;
  isActive: boolean;
  productCount: number;
  childCount: number;
};
export type BrandRow = { id: string; name: string; isActive: boolean; productCount: number };
export type UnitRow = { code: string; name: string; isActive: boolean; productCount: number };

export type StockRow = Level & { product: ProductRef; warehouse: Ref; reorderPoint: number; state: StockState; value: number };
/** One page of the stock list: `total` sums every matching row, `count` is how many there are. */
export type StockOverview = { items: StockRow[]; total: Level & { value: number }; count: number };

export type MovementKind =
  | "receive"
  | "issue"
  | "transfer_out"
  | "transfer_in"
  | "adjust"
  | "return_in"
  | "return_out"
  | "damage"
  | "write_off"
  | "expired"
  | "lost"
  | "reserve"
  | "release";

export type Movement = {
  id: number;
  at: string;
  kind: MovementKind;
  product: ProductRef;
  warehouse: Ref;
  location: { id: string; code: string; name: string } | null;
  batch: { id: string; batchNo: string; expiresOn: string | null } | null;
  quantity: number;
  onHandChange: number;
  onHandAfter: number | null;
  unitCost: number;
  reference: string | null;
  referenceType: string | null;
  referenceId: string | null;
  note: string | null;
  serials: string[];
  user: string;
};
export type Page<T> = { items: T[]; more: boolean };

/** One page of a list the server pages: its rows and how many match in all. */
export type Paged<T> = { items: T[]; total: number };

export type BatchRow = BatchRef & {
  product: ProductRef;
  onHand: number;
  damaged: number;
  daysLeft: number | null;
  value: number;
  warehouses: { code: string; onHand: number }[];
};

export type SerialRow = {
  id: string;
  serialNo: string;
  status: "in_stock" | "in_transit" | "issued" | "written_off";
  product: ProductRef;
  warehouse: Ref | null;
  location: { id: string; code: string; name: string } | null;
  batch: BatchRef | null;
  history: Movement[];
};

export type WarehouseRow = Ref & { address: string | null; isActive: boolean; locationCount: number; units: number; value: number; products: number; qualityCheck?: boolean };

/** A file kept with an item, and whether it goes with every sale (step 15e). */
export type ProductDocument = { id: string; productId: string; name: string; fileName: string; contentType: string; size: number; sendWithSales: boolean; createdAt: string; href: string };

/** Replenishment (step 15a). */
export type ReplenishmentSettings = { safetyDays: number; defaultLeadDays: number; historyDays: number; automatic: boolean; lastRunAt: string | null };
export type ReplenishmentRow = {
  product: ProductRef; supplier: { id: string; code?: string; name: string } | null; available: number; inTransit: number; onOrder: number; dailyUse: number;
  leadDays: number; safetyDays: number; orderPoint: number; position: number; suggested: number; daysLeft: number | null; unitCost: number;
};

/** A pack of an item and how many of its base unit it holds (step 14e). */
export type PackagingRow = { id: string; name: string; quantity: number; barcode: string | null };

/** A delivery's packages (step 14d). */
export type Packing = {
  packages: { id: string; number: string; index: number; of: number; weightGrams: number | null; notes: string | null; packedBy: Person | null; createdAt: string;
              lines: { lineId: string; product: ProductRef; quantity: number }[] }[];
  lines: { lineId: string; product: ProductRef; quantity: number; packed: number }[];
  allPacked: boolean;
};

/** Several held deliveries picked together (step 14d). */
export type WaveBrief = {
  id: string; number: string; status: "open" | "done"; warehouse: Ref; notes: string | null; createdBy: Person | null; createdAt: string; doneAt: string | null;
  orders: { id: string; number: string; recipient: string; status: string; units: number }[]; units: number;
};
export type Wave = WaveBrief & {
  pickList: { product: ProductRef; total: number; short: number; from: { location: { id: string; code: string }; batch: { id: string; batchNo: string; expiresOn: string | null } | null; quantity: number }[];
              orders: { orderId: string; number: string; recipient: string; quantity: number }[] }[];
};

/** A cycle count that comes round every so many days (step 14b). */
export type CountSchedule = {
  id: string; name: string; warehouse: Ref; category: { id: string; name: string } | null; everyDays: number; nextOn: string; lastCountedOn: string | null;
  isActive: boolean; due: boolean; overdueDays: number; openCount: { id: string; number: string; status: string } | null; createdAt: string;
};

/** A receipt's quality check (step 14a). */
export type QualityCheckBrief = {
  id: string; number: string; status: "waiting" | "done";
  receipt: { id: string; number: string }; supplier: { id: string; name: string } | null; warehouse: { id: string; code: string; name: string };
  receivedAt: string | null; checkedBy: { id: string; name: string } | null; checkedAt: string | null; units: number; passed: number; failed: number; createdAt: string | null;
};
export type QualityCheck = QualityCheckBrief & {
  notes: string | null;
  lines: { id: string; product: ProductRef; location: { id: string; code: string; name: string }; batch: { id: string; batchNo: string; expiresOn: string | null } | null;
           quantity: number; passed: number | null; failed: number | null; reason: string | null; reasonLabel: string | null; note: string | null }[];
  reasons: { value: string; label: string }[];
};
export type Warehouse = WarehouseRow & {
  createdAt: string;
  summary: Level;
  lowCount: number;
  locations: { id: string; code: string; name: string; isDefault: boolean; isActive: boolean; units: number; products: number }[];
};

export type Performance = {
  orders: number;
  ordered: number;
  received: number;
  spend: number;
  onTime: number;
  late: number;
  averageLeadDays: number | null;
  fillRate: number | null;
  onTimeRate: number | null;
} | null;

export type Contact = { name: string; role: string | null; email: string | null; phone: string | null };

export type SupplierRow = Ref & {
  contactPerson: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  contacts: Contact[];
  paymentTerms: string | null;
  leadTimeDays: number | null;
  notes: string | null;
  isActive: boolean;
  /** Tax registration, for Finance's bills and the BIR's purchase lists. */
  tin: string | null;
  vatStatus: "vat" | "non_vat";
  defaultAtc: string | null;
  /** What it bills in: PHP, or USD for suppliers abroad. */
  currency: string;
  performance: Performance;
};
export type Supplier = SupplierRow & {
  createdAt: string;
  prices: { product: ProductRef; supplierSku: string | null; price: number; leadTimeDays: number | null; updatedAt: string }[];
  products: ProductRef[];
  orders: POBrief[];
};

export type POStatus = "draft" | "ordered" | "partial" | "received" | "cancelled";
export type POBrief = {
  id: string;
  number: string;
  status: POStatus;
  supplier: Ref;
  warehouse: Ref;
  orderedOn: string | null;
  expectedOn: string | null;
  late: boolean;
  lineCount: number;
  ordered: number;
  received: number;
  total: number;
  createdAt: string;
  /** Its lines, short, for a list row that opens in place. */
  items: { sku: string; product: string; quantity: number; received: number; unitCost: number }[];
};
export type PO = POBrief & POExtras & {
  notes: string | null;
  createdBy: Person;
  orderedBy: Person;
  lines: { id: string; product: ProductRef; quantity: number; received: number; outstanding: number; unitCost: number; total: number }[];
  receipts: ReceiptBrief[];
};
export type Backorder = {
  order: { id: string; number: string; status: POStatus; expectedOn: string | null; late: boolean };
  supplier: Ref;
  warehouse: Ref;
  product: ProductRef;
  ordered: number;
  received: number;
  outstanding: number;
  value: number;
};

export type ReceiptBrief = {
  id: string;
  /** One document header (step 8). */
  header: DocumentHeader;
  number: string;
  order: { id: string; number: string } | null;
  supplier: Ref | null;
  warehouse: Ref;
  location: { id: string; code: string; name: string };
  deliveryRef: string | null;
  receivedAt: string;
  receivedBy: Person;
  units: number;
  total: number;
};
export type POExtras = {
  /** Raised for a sales order (order-on-demand 15b, dropship 15c), or made by replenishment (15a). */
  salesOrder?: { id: string; number: string } | null; dropship?: boolean; shipTo?: { name: string | null; address: string | null } | null; replenishment?: boolean;
};

export type Receipt = ReceiptBrief & {
  notes: string | null;
  /** Its quality check, when its warehouse checks what it receives (step 14a). */
  qualityCheck?: { id: string; number: string; status: "waiting" | "done" } | null;
  lines: { id: string; product: ProductRef; quantity: number; unitCost: number; total: number; batch: BatchRef | null; serials: string[] }[];
};

export type OrderKind = "sale" | "internal" | "department" | "project" | "distribution";
export type OrderStatus = "draft" | "confirmed" | "picking" | "issued" | "cancelled";
export type Pick = { locationId: string; locationCode: string; batchId: string | null; batchNo: string | null; expiresOn: string | null; quantity: number };

/** A delivery company (step 12). */
export type Courier = { id: string; code: string; name: string; trackingUrl: string | null; sortOrder: number; isActive: boolean };
export type DeliveryMethod = "courier" | "own" | "pickup";
/** How a customer's delivery goes and where it is (step 12). */
export type Shipping = {
  method: DeliveryMethod | null;
  methodLabel: string | null;
  courier: { id: string; name: string } | null;
  trackingNumber: string | null;
  trackingUrl: string | null;
  fee: number;
  feeCharged: boolean;
  status: "out" | "delivered" | "failed" | null;
  statusLabel: string | null;
  deliveredAt: string | null;
  onTime: boolean | null;
  failedReason: string | null;
  attempts: number;
  hasPhoto: boolean;
};

export type OrderBrief = {
  id: string;
  /** One document header (step 8). */
  header: DocumentHeader;
  number: string;
  kind: OrderKind;
  recipient: string;
  status: OrderStatus;
  warehouse: Ref;
  neededOn: string | null;
  lineCount: number;
  units: number;
  total: number;
  createdAt: string;
  confirmedAt: string | null;
  issuedAt: string | null;
  /** Its lines, short, for a list row that opens in place. */
  items: { sku: string; product: string; quantity: number; unitPrice: number }[];
  /** A customer's delivery's shipping (step 12); null for an issue to a department or project. */
  shipping?: Shipping | null;
  /** The wave it is picked in (step 14d). */
  waveId?: string | null;
};
export type Order = OrderBrief & {
  /** Proof of delivery: who signed for it, and their signature (step 10). */
  received?: { name: string; signedAt: string; signature: string | null; fingerprint: string } | null;
  notes: string | null;
  createdBy: Person;
  confirmedBy: Person;
  issuedBy: Person;
  lines: { id: string; product: ProductRef; quantity: number; unitPrice: number; total: number; available: number | null; picks: Pick[]; serials: string[] }[];
};
export type Reservation = {
  order: { id: string; number: string; status: OrderStatus; recipient: string; neededOn: string | null };
  warehouse: Ref;
  product: ProductRef;
  quantity: number;
  state: "reserved" | "allocated";
};

export type TransferStatus = "draft" | "requested" | "approved" | "in_transit" | "received" | "cancelled";
export type TransferBrief = {
  id: string;
  /** One document header (step 8). */
  header: DocumentHeader;
  number: string;
  status: TransferStatus;
  from: Ref;
  to: Ref;
  lineCount: number;
  units: number;
  createdAt: string;
  requestedAt: string | null;
  dispatchedAt: string | null;
  receivedAt: string | null;
};
export type Transfer = TransferBrief & {
  notes: string | null;
  createdBy: Person;
  requestedBy: Person;
  approvedBy: Person;
  approvedAt: string | null;
  dispatchedBy: Person;
  receivedBy: Person;
  lines: { id: string; product: ProductRef; quantity: number; available: number | null; picks: Pick[]; serials: string[] }[];
};

export type AdjustmentReason = "count" | "found" | "other" | "customer_return" | "supplier_return" | "damaged" | "write_off" | "expired" | "lost";
export type ReasonOption = { key: AdjustmentReason; label: string; direction: "adds" | "removes" | "either" };
export type AdjustmentBrief = {
  id: string;
  /** One document header (step 8). */
  header: DocumentHeader;
  number: string;
  status: "pending" | "posted" | "rejected";
  reason: AdjustmentReason;
  reasonLabel: string;
  warehouse: Ref;
  lineCount: number;
  units: number;
  value: number;
  countId: string | null;
  createdAt: string;
  createdBy: Person;
  decidedBy: Person;
  decidedAt: string | null;
};
export type Adjustment = AdjustmentBrief & {
  notes: string | null;
  lines: { id: string; product: ProductRef; location: { id: string; code: string; name: string }; batch: BatchRef | null; quantity: number; value: number; serials: string[] }[];
};

export type CountStatus = "open" | "submitted" | "approved" | "cancelled";
export type CountBrief = {
  id: string;
  /** One document header (step 8). */
  header: DocumentHeader;
  number: string;
  status: CountStatus;
  warehouse: Ref;
  category: { id: string; name: string } | null;
  lineCount: number;
  countedCount: number;
  varianceCount: number;
  varianceUnits: number;
  varianceValue: number;
  createdAt: string;
  createdBy: Person;
  approvedBy: Person;
  approvedAt: string | null;
};
export type Count = CountBrief & {
  notes: string | null;
  submittedBy: Person;
  adjustmentId: string | null;
  lines: { id: string; product: ProductRef; location: { id: string; code: string; name: string }; batch: BatchRef | null; expected: number; counted: number | null; difference: number | null; unitCost: number }[];
};

export type Alert = { key: string; tone: "critical" | "warning" | "info"; title: string; count: number; href: string; examples: string[] };

export type Dashboard = {
  totals: { products: number; units: number; value: number; low: number; out: number; expiring: number; reserved: number; inTransit: number };
  warehouses: (Ref & { units: number; value: number; available: number; products: number })[];
  alerts: Alert[];
  recentMovements: Movement[];
  recentReceipts: ReceiptBrief[];
  recentIssues: OrderBrief[];
  /** Orders confirmed or being picked: still to go out. */
  openOrders: number;
  /** The last twelve months, oldest first. */
  trend: { month: string; received: number; issued: number; orders: number }[];
  /** Open purchase orders, soonest expected first. */
  upcoming: PurchaseHome[];
  recentPurchases: PurchaseHome[];
};

export type PurchaseHome = POBrief & { firstItem: string | null; moreItems: number };

/** href: a page of its own listed among the reports (2026-10-28). */
export type ReportInfo = { key: string; title: string; group: string; about: string; dated: boolean; byWarehouse: boolean; fixed?: boolean; href?: string };
export type ReportColumn = { key: string; label: string; kind: "text" | "number" | "money" | "date" | "datetime" | "percent" };
export type Report = ReportInfo & { from: string; to: string; columns: ReportColumn[]; rows: Record<string, string | number | null>[] };

export type AdminUser = {
  id: string;
  email: string;
  fullName: string;
  isActive: boolean;
  role: { id: string; name: string };
  createdAt: string;
  lastSignInAt: string | null;
};
export type AdminUsers = { items: AdminUser[]; roles: { id: string; name: string; description: string | null }[] };
export type PermissionArea = { key: string; name: string; group: string; actions: { key: string; label: string; permission: string }[] };
export type RoleRow = { id: string; name: string; description: string | null; isSystem: boolean; permissions: string[]; userCount: number };
export type RolesData = { roles: RoleRow[]; catalogue: PermissionArea[] };
export type AuditEntry = { id: number; at: string; actor: string; actorId: string | null; action: string; target: string; targetType: string | null; targetId: string | null; fields: string[] };

/** A place on the map. */
export type Pin = { latitude: number; longitude: number };

/** A transfer as the map draws it: a route from one warehouse's pin to the other's. */
export type TransferRoute = TransferBrief & {
  approvedAt: string | null;
  fromPin: Pin | null;
  toPin: Pin | null;
  fromAddress: string | null;
  toAddress: string | null;
  firstItem: string | null;
};

export type MapWarehouse = Ref & { address: string | null; pin: Pin | null };
