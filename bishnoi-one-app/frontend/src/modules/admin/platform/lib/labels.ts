import { percent, type Format } from "@/src/modules/admin/platform/lib/format";
import type {
  AdminAssignment,
  ApprovalReason,
  CustomerStatus,
  GoalStatus,
  GoalUnit,
  ListItem,
  PromoKind,
  PromoTerms,
  Quote,
} from "@/src/modules/admin/platform/lib/types";

// The product. One name, whoever is using it — a company's own name is its
// brandName (Settings → Company) and sits above this, never instead of it.
export const APP_NAME = "Bishnoi One";

// Customer kinds, activity kinds and call outcomes are the company's own words,
// written in Settings → Lists and carried on the session. Lead, active and
// inactive stay Bishnoi One's: the retention maths is built on those three.
export const CUSTOMER_STATUSES: Record<CustomerStatus, string> = {
  lead: "Lead",
  active: "Active",
  inactive: "Inactive",
};

/**
 * What a saved code is called now. A record keeps its code after the company
 * switches the choice off, and a switched-off choice doesn't travel with the
 * session, so the code itself is tidied into words rather than left blank.
 */
export function listName(items: ListItem[], code: string): string {
  const found = items.find((i) => i.code === code);
  if (found) return found.name;
  const words = code.replace(/[_-]+/g, " ").trim();
  return words ? words[0].toUpperCase() + words.slice(1) : code;
}

/**
 * The choices a picker may offer: the switched-on ones, plus whatever this
 * record already carries. A company that stops using a kind shouldn't have it
 * offered again, but the customer already filed under it must still open.
 */
export function pickable(items: ListItem[], keep?: string | null): ListItem[] {
  return items.filter((i) => i.isActive || i.code === keep);
}

export const ACTION_LABELS: Record<string, string> = {
  view: "View",
  create: "Add",
  edit: "Edit",
  delete: "Delete",
  report: "Reports",
  prices: "Prices",
  manage: "Manage",
};

/** 0.5 -> "50%"; null (nobody to measure) -> "—". */
export function rateLabel(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}

/** A goal's value or target in its unit: "80%", "48K" in the company's money, "12", "1.5 days". */
export function goalValue(fmt: Format, unit: GoalUnit, value: number | null, exact = false): string {
  if (value === null) return "—";
  switch (unit) {
    case "percent":
      return `${Math.round(value / 100)}%`;
    case "money":
      return exact ? fmt.peso(value) : fmt.pesoCompact(value);
    case "days":
      return `${value} ${value === 1 ? "day" : "days"}`;
    case "count":
      return fmt.count(value);
  }
}

export const GOAL_STATUSES: Record<GoalStatus, string> = {
  met: "Met",
  on_pace: "On pace",
  behind: "Behind pace",
  below: "Below target",
  over: "Over target",
  no_data: "No data yet",
};

export const PROMO_KINDS: Record<PromoKind, string> = {
  percent: "Percent off",
  amount: "Amount off each",
  free_goods: "Free goods",
  tiered: "Volume tiers",
};

export const QUOTE_STATES: Record<Quote["state"], string> = {
  waiting: "Waiting on Finance",
  ready: "Ready",
  rejected: "Rejected",
};

export const APPROVAL_STATUSES: Record<Quote["approval"]["status"], string> = {
  none: "Not needed",
  pending: "Waiting",
  approved: "Approved",
  rejected: "Rejected",
};

export const LETTER_STATUSES: Record<NonNullable<Quote["letter"]>["status"], string> = {
  pending: "To check",
  verified: "Verified",
  rejected: "Rejected",
};

export const PAYMENT_STATUSES: Record<Quote["payment"]["status"], string> = {
  none: "—",
  unpaid: "Unpaid",
  partial: "Part paid",
  paid: "Paid",
};

export function approvalReason(reason: ApprovalReason, quote: Pick<Quote, "priceTypeName">): string {
  return reason === "price" ? `${quote.priceTypeName} needs Finance's approval` : "Discount is over the division's limit";
}

/** "10% off", "10.00 off each" in the company's money, "Buy 10, get 1 free", "5% from 20 · 8% from 50". */
export function promoTerms(fmt: Format, p: Pick<PromoTerms, "kind" | "percentBp" | "amountCentavos" | "buyQty" | "freeQty" | "tiers">): string {
  switch (p.kind) {
    case "percent":
      return `${percent(p.percentBp ?? 0)} off`;
    case "amount":
      return `${fmt.peso(p.amountCentavos ?? 0)} off each`;
    case "free_goods":
      return `Buy ${p.buyQty}, get ${p.freeQty} free`;
    case "tiered":
      return p.tiers.map((t) => `${percent(t.percentBp)} from ${t.minQty}`).join(" · ");
  }
}

/** "B&B · MD Telesales", or "Finance · All divisions": the module, then where, without saying B&B twice. */
export function accessLabel(a: AdminAssignment): string {
  if (a.moduleKey === "settings") return "Settings";
  return a.divisionCode === a.moduleKey ? a.scopeLabel : `${a.moduleName} · ${a.scopeLabel}`;
}
