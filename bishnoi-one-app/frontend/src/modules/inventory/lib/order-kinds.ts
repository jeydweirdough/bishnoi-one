import type { IconName } from "@/src/modules/inventory/platform/ui/icons";
import type { OrderKind } from "@/src/modules/inventory/lib/types";

// Each kind of order has its own place: a list, a New button and a form made
// for it, rather than one form that asks what it is. What differs is who it's
// for (a customer, a department, a project), whether it's priced, and how it
// reads. Stock goes out the same way for all of them: reserved, picked, issued.

export type KindInfo = {
  kind: OrderKind;
  /** In the address: /orders/new/customer. */
  slug: string;
  /** The list: "Customer orders". */
  plural: string;
  /** One of them: "customer order". */
  one: string;
  /** The New button, and the form's title. */
  newLabel: string;
  intro: string;
  icon: IconName;
  /** Who it's for. */
  recipient: { label: string; placeholder: string; hint: string };
  /** The notes field: what it's for, for internal use. */
  notes: { label: string; hint?: string };
  /** Customer orders carry a selling price per line. */
  priced: boolean;
};

export const KINDS: KindInfo[] = [
  {
    kind: "sale",
    slug: "customer",
    plural: "Customer orders",
    one: "customer order",
    newLabel: "New customer order",
    intro: "Stock sold to a customer: hospitals, pharmacies, clinics and doctors. Priced per line.",
    icon: "issuance",
    recipient: { label: "Customer", placeholder: "St. Luke's Family Clinic", hint: "The customer buying the stock." },
    notes: { label: "Notes" },
    priced: true,
  },
  {
    kind: "internal",
    slug: "internal",
    plural: "Internal use",
    one: "internal use",
    newLabel: "New internal use issue",
    intro: "Stock the company uses itself: samples, demonstrations, the office.",
    icon: "company",
    recipient: { label: "Used by", placeholder: "Field team, Manila", hint: "The person or team using the stock." },
    notes: { label: "Purpose", hint: "Recorded in the stock movement history." },
    priced: false,
  },
  {
    kind: "department",
    slug: "department",
    plural: "Department requests",
    one: "department request",
    newLabel: "New department request",
    intro: "Stock a department asks for: the pharmacy, nursing, the laboratory.",
    icon: "teams",
    recipient: { label: "Department", placeholder: "Nursing", hint: "The requesting department." },
    notes: { label: "Notes" },
    priced: false,
  },
  {
    kind: "project",
    slug: "project",
    plural: "Projects",
    one: "project issue",
    newLabel: "Issue to a project",
    intro: "Stock set aside for a project, so its use is counted against it.",
    icon: "goals",
    recipient: { label: "Project", placeholder: "Medical mission, Davao", hint: "The project the stock is issued to." },
    notes: { label: "Notes" },
    priced: false,
  },
  {
    kind: "distribution",
    slug: "distribution",
    plural: "Distributions",
    one: "distribution",
    newLabel: "New distribution",
    intro: "Stock given out to a program, a site or a partner.",
    icon: "distribution",
    recipient: { label: "Distributed to", placeholder: "Barangay health centre, Pasig", hint: "The recipient of the stock." },
    notes: { label: "Notes" },
    priced: false,
  },
];

export const kindOf = (k: string | null | undefined) => KINDS.find((x) => x.kind === k);
export const kindBySlug = (slug: string) => KINDS.find((x) => x.slug === slug);
export const listHref = (k: KindInfo) => `/inventory/orders?kind=${k.kind}`;
export const newHref = (k: KindInfo) => `/inventory/orders/new/${k.slug}`;
