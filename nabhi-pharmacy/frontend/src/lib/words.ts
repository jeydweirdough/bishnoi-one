// The Pharmacy's words for its states, the same on every screen.

import type { BatchStatus, MedicineStatus, MovementKind, PaymentMethod, PrescriptionStatus, RxClass } from "./types";

export const RX_CLASSES: Record<RxClass, string> = {
  otc: "Over the counter",
  rx: "Prescription",
  dangerous: "Dangerous drug",
};

export const RX_CLASS_HINTS: Record<RxClass, string> = {
  otc: "Sold at the counter, no prescription needed.",
  rx: "Dispensed only against a verified prescription.",
  dangerous: "A prescription medicine under stricter control: the prescriber's licence number is required.",
};

export const MEDICINE_STATUSES: Record<MedicineStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  discontinued: "Discontinued",
};

export const MEDICINE_STATUS_HINTS: Record<MedicineStatus, string> = {
  active: "Stocked and given out.",
  inactive: "Paused: kept on record, can't be verified on a prescription.",
  discontinued: "Not coming back. What's left can still be given out.",
};

export const PRESCRIPTION_STATUSES: Record<PrescriptionStatus, string> = {
  received: "Received",
  pending: "Checking",
  verified: "Verified",
  needs_clarification: "Needs clarification",
  rejected: "Rejected",
};

export const BATCH_STATUSES: Record<BatchStatus, string> = {
  available: "Available",
  quarantined: "Quarantined",
  recalled: "Recalled",
};

export const PAYMENT_METHODS: Record<PaymentMethod, string> = {
  cash: "Cash",
  card: "Card",
  ewallet: "E-wallet",
  other: "Other",
};

export const MOVEMENT_KINDS: Record<MovementKind, string> = {
  receive: "Received",
  dispense: "Dispensed",
  sale: "Sold",
  adjust: "Adjusted",
  return: "Returned",
};

export const DOSAGE_FORMS = ["tablet", "capsule", "syrup", "suspension", "drops", "cream", "ointment", "injection", "inhaler", "sachet"];

/** "Amoxicillin 500mg · 21 capsules" for a line of a list. */
export function itemsLine(items: { writtenAs: string; quantity: number }[]): string {
  return items.map((i) => `${i.writtenAs} × ${i.quantity}`).join(" · ");
}

/** How old someone is, from their birth date, for the check screen. */
export function age(birthDate: string | null, today = new Date()): number | null {
  if (!birthDate) return null;
  const born = new Date(`${birthDate}T00:00:00Z`);
  let years = today.getUTCFullYear() - born.getUTCFullYear();
  const m = today.getUTCMonth() - born.getUTCMonth();
  if (m < 0 || (m === 0 && today.getUTCDate() < born.getUTCDate())) years -= 1;
  return years;
}
