// What the Pharmacy API sends, as the screens read it. Money is in centavos.

export type RxClass = "otc" | "rx" | "dangerous";
export type MedicineStatus = "active" | "inactive" | "discontinued";
export type PrescriptionStatus = "received" | "pending" | "verified" | "needs_clarification" | "rejected";
export type DispenseState = "none" | "partial" | "full";
export type BatchStatus = "available" | "quarantined" | "recalled";
export type PaymentMethod = "cash" | "card" | "ewallet" | "other";
export type MovementKind = "receive" | "dispense" | "sale" | "adjust" | "return";
export type PersonKind = "patient" | "customer";

export type Person = { id: string; name: string; licenseNo: string | null };
export type Named = { id: string; name: string };

export type Category = { id: string; name: string; description: string | null; isActive: boolean; medicineCount: number };
export type Brand = { id: string; name: string; manufacturer: string | null; isActive: boolean; medicineCount: number };

export type Medicine = {
  id: string;
  code: string;
  genericName: string;
  label: string;
  brand: Named | null;
  category: Named | null;
  strength: string | null;
  dosageForm: string;
  unit: string;
  rxClass: RxClass;
  priceCentavos: number;
  reorderLevel: number;
  status: MedicineStatus;
  notes: string | null;
  onHand: number | null;
  available: number | null;
  updatedAt: string;
};

export type MedicineBatch = {
  id: string;
  lotNo: string;
  expiresOn: string;
  qtyOnHand: number;
  qtyReceived: number;
  status: BatchStatus;
  expired: boolean;
  supplier: string | null;
};

export type MedicineDetail = Medicine & { batches: MedicineBatch[] };
export type MedicineReference = { categories: Category[]; brands: Brand[] };

export type PatientBrief = { id: string; fullName: string; birthDate: string | null; allergies: string | null; kind: PersonKind };

export type Patient = {
  id: string;
  kind: PersonKind;
  fullName: string;
  birthDate: string | null;
  sex: "female" | "male" | "other" | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  allergies: string | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
};

export type PatientRow = Patient & { prescriptionCount: number; lastVisitAt: string | null };

export type PatientDetail = Patient & {
  prescriptions: {
    id: string;
    number: string;
    status: PrescriptionStatus;
    prescriberName: string;
    prescribedOn: string;
    receivedAt: string;
    items: { writtenAs: string; quantity: number; qtyDispensed: number }[];
  }[];
  medications: {
    at: string;
    medicine: string;
    medicineId: string;
    rxClass: RxClass;
    quantity: number;
    unit: string;
    lotNo: string;
    saleId: string;
    saleNumber: string;
    dispensingNumber: string | null;
  }[];
};

export type PrescriptionSummary = {
  id: string;
  number: string;
  status: PrescriptionStatus;
  dispensed: DispenseState;
  patient: PatientBrief;
  prescriberName: string;
  prescribedOn: string;
  receivedAt: string;
  checkedAt: string | null;
  checkedBy: Person | null;
  itemCount: number;
  items: { writtenAs: string; quantity: number; remaining: number }[];
  ready?: boolean;
  /** Sent in by another Bishnoi One app (e.g. a CRM quote) for the pharmacist's
   *  check. That app fills it from its own order, so it's never dispensed here. */
  source: RxSource | null;
};

export type RxSource = { app: string; reference: string | null; sentBy: string | null };

export type PrescriptionItem = {
  id: string;
  writtenAs: string;
  medicine: { id: string; label: string; unit: string; rxClass: RxClass; status: MedicineStatus; priceCentavos: number } | null;
  quantity: number;
  directions: string | null;
  qtyDispensed: number;
  remaining: number;
  available: number | null;
};

export type Flag = { level: "block" | "warn"; check: string; message: string };

export type Prescription = Omit<PrescriptionSummary, "items"> & {
  prescriberLicense: string | null;
  prescriberClinic: string | null;
  notes: string | null;
  receivedBy: Person | null;
  verificationNotes: string | null;
  checks: { key: string; label: string; done: boolean }[];
  items: PrescriptionItem[];
  flags: Flag[];
  editable: boolean;
  dispensings: { id: string; number: string; dispensedAt: string; dispensedBy: Person | null; units: number }[];
};

export type PrescriptionCounts = { inbox: number; pending: number; verified: number; attention: number };

export type PreparedItem = {
  id: string;
  writtenAs: string;
  directions: string | null;
  quantity: number;
  qtyDispensed: number;
  remaining: number;
  medicine: { id: string; label: string; unit: string; priceCentavos: number };
  batches: { id: string; lotNo: string; expiresOn: string; qtyOnHand: number }[];
};

export type Prepared = Omit<PrescriptionSummary, "items"> & { items: PreparedItem[] };

export type Dispensing = {
  id: string;
  number: string;
  prescription: { id: string; number: string };
  patient: PatientBrief;
  dispensedBy: Person | null;
  dispensedAt: string;
  notes: string | null;
  saleId: string | null;
  lines: { medicine: string; medicineId: string; unit: string; lotNo: string; expiresOn: string; quantity: number }[];
  units: number;
};

export type SaleLine = {
  id: string;
  medicine: string;
  medicineId: string;
  unit: string;
  lotNo: string;
  quantity: number;
  qtyReturned: number;
  unitPriceCentavos: number;
  lineTotalCentavos: number;
};

export type SaleReturn = {
  id: string;
  number: string;
  sale: { id: string; number: string };
  patient: PatientBrief | null;
  reason: string;
  restocked: boolean;
  refundCentavos: number;
  refundMethod: PaymentMethod | null;
  by: Person | null;
  at: string;
  units: number;
};

export type Sale = {
  id: string;
  number: string;
  source: "counter" | "dispensing";
  patient: PatientBrief | null;
  soldBy: Person | null;
  soldAt: string;
  subtotalCentavos: number;
  discountCentavos: number;
  totalCentavos: number;
  refundedCentavos: number;
  paymentMethod: PaymentMethod;
  notes: string | null;
  dispensing: { id: string; number: string; prescriptionId: string } | null;
  lines: SaleLine[];
};

export type SaleDetail = Sale & { returns: SaleReturn[] };
export type SaleList = { items: Sale[]; count: number; totalCentavos: number; refundedCentavos: number };

export type Batch = {
  id: string;
  medicine: { id: string; label: string; code: string; unit: string };
  lotNo: string;
  supplier: Named | null;
  receivingId: string | null;
  manufacturedOn: string | null;
  expiresOn: string;
  daysToExpiry: number;
  expired: boolean;
  costCentavos: number;
  qtyReceived: number;
  qtyOnHand: number;
  valueCentavos: number;
  status: BatchStatus;
  statusReason: string | null;
  statusChangedAt: string | null;
};

export type BatchList = { items: Batch[]; valueCentavos: number; withinDays: number };

export type StockRow = {
  medicine: { id: string; label: string; code: string; unit: string; status: MedicineStatus; rxClass: RxClass };
  onHand: number;
  available: number;
  reorderLevel: number;
  low: boolean;
  valueCentavos: number;
  nearestExpiry: string | null;
};

export type Receiving = {
  id: string;
  number: string;
  supplier: Named | null;
  reference: string | null;
  receivedOn: string;
  notes: string | null;
  receivedBy: Person | null;
  createdAt: string;
  lineCount: number;
  units: number;
  lines?: { medicine: string; medicineId: string; lotNo: string; expiresOn: string; quantity: number; costCentavos: number; batchId: string }[];
};

export type Movement = {
  id: number;
  at: string;
  kind: MovementKind;
  medicine: { id: string; label: string; unit: string };
  batch: { id: string; lotNo: string };
  quantity: number;
  balance: number;
  reason: string | null;
  reference: string | null;
  by: Person | null;
};

export type Supplier = {
  id: string;
  name: string;
  contactPerson: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
  isActive: boolean;
  deliveryCount: number;
  lastDeliveryOn: string | null;
  updatedAt: string;
};

export type SupplierDetail = Supplier & {
  deliveries: { id: string; number: string; reference: string | null; receivedOn: string }[];
  batches: { id: string; medicine: string; lotNo: string; expiresOn: string; qtyOnHand: number; status: BatchStatus }[];
};

export type Dashboard = {
  today: string;
  prescriptions: { inbox: number; pending: number; needsClarification: number };
  dispensing: { queue: number; partial: number; today: number; unitsToday: number };
  stock: {
    low: number;
    expiring: number;
    expired: number;
    quarantined: number;
    lowItems: { id: string; label: string; available: number; reorderLevel: number; unit: string }[];
  };
  sales: { count: number; totalCentavos: number };
  expiryWarningDays: number;
};

// --- Administration ---

export type RoleOption = { id: string; name: string; description: string | null };

export type AdminUser = {
  id: string;
  email: string;
  fullName: string;
  licenseNo: string | null;
  isActive: boolean;
  role: { id: string; name: string };
  createdAt: string;
  lastSignInAt: string | null;
};

export type RoleRow = { id: string; name: string; description: string | null; isSystem: boolean; permissions: string[]; userCount: number };

export type PermissionArea = {
  key: string;
  name: string;
  group: string;
  actions: { key: string; label: string; permission: string }[];
};

export type AuditItem = {
  id: number;
  at: string;
  actor: string;
  actorId: string | null;
  action: string;
  target: string;
  targetType: string | null;
  fields: string[];
};

// Promotional material designs Admin sends for the pharmacist's approval.
export type MaterialReviewStatus = "waiting" | "approved" | "returned" | "rejected";

export type MaterialReview = {
  id: string;
  number: string;
  source: string;
  reference: string;
  version: number;
  title: string;
  kind: string;
  product: string | null;
  description: string | null;
  notes: string | null;
  fileName: string;
  contentType: string;
  sentBy: string;
  status: MaterialReviewStatus;
  comments: string | null;
  reviewedBy: string | null;
  reviewedByLicense: string | null;
  reviewedAt: string | null;
  receivedAt: string;
};

export type MaterialReviewDetail = { review: MaterialReview; earlier: MaterialReview[]; canDecide: boolean };
