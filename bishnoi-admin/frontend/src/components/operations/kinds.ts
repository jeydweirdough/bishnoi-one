// The four trackers moved in from the JASMINE TASKS workbook, each described
// once: its words, its form's fields, its table's columns, its record page
// (facts, quick steps, details) and its filter. The list (screens/operations.tsx),
// the record page (screens/operation-record.tsx) and the form (record-form.tsx)
// draw them all, in the CRM's design.

import type { IconName } from "@/src/platform/ui/icons";
import type { OperationsPath } from "@/src/actions/operations";

export type Item = Record<string, unknown> & { id: string };

export type Field = {
  key: string;
  label: string;
  type: "text" | "date" | "number" | "money" | "choice" | "long";
  options?: Record<string, string>;
  required?: boolean;
  wide?: boolean;
  hint?: string;
  placeholder?: string;
};

export type Tone = "outline" | "good" | "warn" | "bad" | "info" | "mute";
export type Cell =
  | { type: "who"; name: string; sub?: string | null; filled?: boolean }
  | { type: "text"; text: string | null; sub?: string | null }
  | { type: "due"; date: string | null; days: number | null; note?: string }
  | { type: "tag"; text: string; tone: Tone; dot?: boolean }
  | { type: "money"; text: string };

export type Kind = {
  path: OperationsPath;
  /** Where its pages are: /vehicles, /fuel-cards, /travel, /devices. */
  route: string;
  area: "vehicles" | "travel" | "devices";
  title: string;
  icon: IconName;
  intro: string;
  one: string; // "vehicle": "New vehicle", "Delete this vehicle?"
  fields: Field[];
  name: (i: Item) => string;
  /** The table: its columns, the first being the name. */
  columns: { key: string; label: string; cell: (i: Item) => Cell; kind?: "num" | "hide-sm" }[];
  /** The one switch above the table. */
  filter?: { label: string; options: Record<string, string>; matches: (i: Item, key: string) => boolean };
  search: (i: Item) => string;
  /** The record page: the line under the name, its tag, its four facts. */
  subline: (i: Item) => string;
  status: (i: Item) => { text: string; tone: Tone } | null;
  facts: (i: Item) => { label: string; value: string }[];
  /** Quick steps the API takes for it (POST /{path}/{id}/log), in the order shown; the first may be the page's main button. */
  steps: { action: string; label: string; primary?: (i: Item) => boolean }[];
  details: (i: Item) => { title: string; rows: { label: string; value: string | null }[] }[];
};

const s = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));
export const day = (v: unknown) => (typeof v === "string" && v ? new Date(`${v.slice(0, 10)}T00:00:00`).toLocaleDateString("en-PH", { day: "numeric", month: "short", year: "numeric" }) : null);
const peso = (v: unknown) => (typeof v === "number" ? `₱${v.toLocaleString("en-PH", { maximumFractionDigits: 0 })}` : null);
const daysTo = (iso: unknown) => (typeof iso === "string" && iso ? Math.round((new Date(`${iso}T00:00:00`).getTime() - new Date(new Date().toDateString()).getTime()) / 864e5) : null);

export const FLEET_STATUS = { processing: "Processing", handed_over: "Handed over", with_hr: "With HR", returned: "Returned" };
export const CARD_STATE = { active: "Active", blocked: "Blocked" };
export const TRAVEL_STATUS = { for_approval: "For approval", for_processing: "For processing", approved: "Approved", booked: "Booked", cancelled: "Cancelled" };
export const TRAVEL_KIND = { hotel: "Hotel stay", flight: "Flight" };
export const CONDITION = { brand_new: "Brand new", repaired: "Repaired", used: "Used" };

/** A vehicle's state in one tag: the worst of its three dates. */
function vehicleStatus(i: Item): { text: string; tone: Tone } {
  const dues = (i.dues as { label: string; daysRemaining: number }[]) ?? [];
  if (dues.length === 0) return { text: "Dates missing", tone: "mute" };
  const late = dues.find((d) => d.daysRemaining < 0);
  if (late) return { text: `${late.label.replace(" (PMS)", "")} overdue`, tone: "bad" };
  const soon = dues.find((d) => d.daysRemaining <= 30);
  return soon ? { text: `${soon.label.replace(" (PMS)", "")} due soon`, tone: "warn" } : { text: "Current", tone: "good" };
}

function tripStatus(i: Item): { text: string; tone: Tone } {
  const days = i.daysRemaining as number | null;
  if (i.status === "cancelled") return { text: "Cancelled", tone: "mute" };
  if (typeof days === "number" && days < 0) return { text: "Took place", tone: "mute" };
  const tone: Tone = i.status === "booked" ? "good" : i.status === "approved" ? "info" : "warn";
  return { text: TRAVEL_STATUS[i.status as keyof typeof TRAVEL_STATUS] ?? s(i.status), tone };
}

export const KINDS: Record<OperationsPath, Kind> = {
  vehicles: {
    path: "vehicles",
    route: "/vehicles",
    area: "vehicles",
    title: "Vehicles",
    icon: "vehicles",
    intro: "Registration, insurance and maintenance (PMS)",
    one: "vehicle",
    fields: [
      { key: "name", label: "Vehicle", type: "text", required: true, placeholder: "Ford Ranger AT" },
      { key: "plate", label: "Plate number", type: "text" },
      { key: "yearModel", label: "Year model", type: "number" },
      { key: "color", label: "Color", type: "text" },
      { key: "ownerName", label: "Registered owner, and who uses it", type: "text", wide: true, placeholder: "2MG Incorporated / Hermosilla, Michelle" },
      { key: "registrationDue", label: "Registration due", type: "date" },
      { key: "insuranceDue", label: "Insurance due", type: "date" },
      { key: "pmsDue", label: "Next maintenance (PMS)", type: "date" },
      { key: "fleetCard", label: "Fuel card", type: "text" },
      { key: "notes", label: "Notes", type: "long", wide: true },
    ],
    name: (i) => s(i.name),
    columns: [
      { key: "name", label: "Vehicle", cell: (i) => ({ type: "who", name: s(i.name), sub: [i.plate, i.yearModel, i.color].filter(Boolean).join(" · "), filled: vehicleStatus(i).tone === "bad" || vehicleStatus(i).tone === "warn" }) },
      { key: "owner", label: "Owner", kind: "hide-sm", cell: (i) => ({ type: "text", text: s(i.ownerName) || null }) },
      { key: "reg", label: "Registration", cell: (i) => ({ type: "due", date: i.registrationDue as string | null, days: daysTo(i.registrationDue) }) },
      { key: "ins", label: "Insurance", kind: "hide-sm", cell: (i) => ({ type: "due", date: i.insuranceDue as string | null, days: daysTo(i.insuranceDue) }) },
      { key: "pms", label: "Maintenance", kind: "hide-sm", cell: (i) => ({ type: "due", date: i.pmsDue as string | null, days: daysTo(i.pmsDue) }) },
      { key: "status", label: "Status", cell: (i) => ({ type: "tag", ...vehicleStatus(i), dot: true }) },
    ],
    filter: {
      label: "Show",
      options: { soon: "Due in 30 days", overdue: "Overdue", getmeds: "Getmeds", "2mg": "2MG" },
      matches: (i, key) =>
        key === "overdue" ? vehicleStatus(i).tone === "bad" : key === "soon" ? vehicleStatus(i).tone === "warn" : s(i.ownerName).toLowerCase().includes(key === "getmeds" ? "getmeds" : "2mg"),
    },
    search: (i) => [i.name, i.plate, i.ownerName, i.color].map(s).join(" "),
    subline: (i) => [i.yearModel, i.color, i.ownerName ? `owned by ${i.ownerName}` : null].filter(Boolean).join(" · "),
    status: (i) => {
      const dues = (i.dues as { label: string; daysRemaining: number }[]) ?? [];
      const next = dues[0];
      if (!next) return { text: "No dates set", tone: "mute" };
      const d = next.daysRemaining;
      return { text: d < 0 ? `${next.label} ${Math.abs(d)} days overdue` : d === 0 ? `${next.label} due today` : `${next.label} due in ${d} days`, tone: d < 0 ? "bad" : d <= 30 ? "warn" : "good" };
    },
    facts: (i) => [
      { label: "Registration", value: day(i.registrationDue) ?? "Not set" },
      { label: "Insurance", value: day(i.insuranceDue) ?? "Not set" },
      { label: "Next PMS", value: day(i.pmsDue) ?? "Not set" },
      { label: "Fuel card", value: s(i.fleetCard) || "None" },
    ],
    steps: [
      // The page's main button settles the soonest date, once it's close.
      { action: "registration_renewed", label: "Registration renewed", primary: (i) => i.nextDue === "Registration" && (daysTo(i.registrationDue) ?? 999) <= 60 },
      { action: "insurance_renewed", label: "Insurance renewed", primary: (i) => i.nextDue === "Insurance" && (daysTo(i.insuranceDue) ?? 999) <= 60 },
      { action: "pms_done", label: "PMS done", primary: (i) => i.nextDue === "Maintenance (PMS)" && (daysTo(i.pmsDue) ?? 999) <= 30 },
    ],
    details: (i) => [
      { title: "The vehicle", rows: [{ label: "Year model", value: s(i.yearModel) || null }, { label: "Color", value: s(i.color) || null }, { label: "Plate number", value: s(i.plate) || null }] },
      { title: "Who has it", rows: [{ label: "Registered owner, and who uses it", value: s(i.ownerName) || null }, { label: "Fuel card", value: s(i.fleetCard) || null }] },
      { title: "Notes", rows: [{ label: "Notes", value: s(i.notes) || null }] },
    ],
  },
  "fleet-cards": {
    path: "fleet-cards",
    route: "/fuel-cards",
    area: "vehicles",
    title: "Fuel cards",
    icon: "fuelCards",
    intro: "Fuel cards given to the sales team",
    one: "fuel card",
    fields: [
      { key: "holderName", label: "Given to", type: "text", required: true },
      { key: "companyName", label: "Company", type: "text", placeholder: "2MG Incorporated" },
      { key: "requestedOn", label: "Asked for on", type: "date" },
      { key: "monthlyAllowance", label: "Monthly allowance (₱)", type: "money" },
      { key: "allowanceNote", label: "Or, the allowance in words", type: "text", hint: "When it isn't pesos, e.g. 200 liters a month." },
      { key: "fuelType", label: "Fuel", type: "text", placeholder: "Unleaded" },
      { key: "plate", label: "Plate number", type: "text" },
      { key: "conductionSticker", label: "Conduction sticker", type: "text", hint: "A new car's, before it has a plate." },
      { key: "vehicleUnit", label: "Vehicle", type: "text", wide: true },
      { key: "status", label: "Where it is", type: "choice", options: FLEET_STATUS, required: true },
      { key: "cardState", label: "Card", type: "choice", options: CARD_STATE, required: true },
      { key: "notes", label: "Notes", type: "long", wide: true },
    ],
    name: (i) => s(i.holderName),
    columns: [
      { key: "name", label: "Given to", cell: (i) => ({ type: "who", name: s(i.holderName), sub: s(i.companyName) || null, filled: i.cardState === "blocked" }) },
      { key: "car", label: "Vehicle", kind: "hide-sm", cell: (i) => ({ type: "text", text: s(i.vehicleUnit) || null, sub: s(i.plate || i.conductionSticker) || null }) },
      { key: "fuel", label: "Fuel", kind: "hide-sm", cell: (i) => ({ type: "text", text: s(i.fuelType) || null }) },
      { key: "where", label: "Where it is", cell: (i) => ({ type: "tag", text: FLEET_STATUS[i.status as keyof typeof FLEET_STATUS] ?? s(i.status), tone: i.status === "processing" ? "warn" : "outline" }) },
      { key: "card", label: "Card", cell: (i) => ({ type: "tag", text: i.cardState === "blocked" ? "Blocked" : "Active", tone: i.cardState === "blocked" ? "bad" : "good", dot: true }) },
      { key: "money", label: "A month", kind: "num", cell: (i) => ({ type: "money", text: peso(i.monthlyAllowance) ?? (s(i.allowanceNote) || "—") }) },
    ],
    filter: {
      label: "Show",
      options: { processing: "Processing", handed_over: "Handed over", with_hr: "With HR", blocked: "Blocked" },
      matches: (i, key) => (key === "blocked" ? i.cardState === "blocked" : i.status === key),
    },
    search: (i) => [i.holderName, i.companyName, i.plate, i.conductionSticker, i.vehicleUnit].map(s).join(" "),
    subline: (i) => [i.companyName, i.vehicleUnit, i.plate || i.conductionSticker].filter(Boolean).map(s).join(" · "),
    status: (i) => (i.cardState === "blocked" ? { text: "Blocked", tone: "bad" } : { text: "Active", tone: "good" }),
    facts: (i) => [
      { label: "A month", value: peso(i.monthlyAllowance) ?? (s(i.allowanceNote) || "Not set") },
      { label: "Fuel", value: s(i.fuelType) || "—" },
      { label: "Where it is", value: FLEET_STATUS[i.status as keyof typeof FLEET_STATUS] ?? s(i.status) },
      { label: "Asked for", value: day(i.requestedOn) ?? "—" },
    ],
    steps: [
      { action: "blocked", label: "Block card" },
      { action: "unblocked", label: "Unblock", primary: (i) => i.cardState === "blocked" },
      { action: "handed_over", label: "Handed over", primary: (i) => i.status === "processing" },
      { action: "with_hr", label: "With HR" },
      { action: "returned", label: "Returned" },
    ],
    details: (i) => [
      { title: "The card", rows: [{ label: "Given to", value: s(i.holderName) }, { label: "Company", value: s(i.companyName) || null }, { label: "Allowance in words", value: s(i.allowanceNote) || null }] },
      { title: "The car", rows: [{ label: "Vehicle", value: s(i.vehicleUnit) || null }, { label: "Plate number", value: s(i.plate) || null }, { label: "Conduction sticker", value: s(i.conductionSticker) || null }] },
      { title: "Notes", rows: [{ label: "Notes", value: s(i.notes) || null }] },
    ],
  },
  travel: {
    path: "travel",
    route: "/travel",
    area: "travel",
    title: "Hotel and flights",
    icon: "travel",
    intro: "Doctors' stays and flights the company pays for",
    one: "sponsorship",
    fields: [
      { key: "doctorName", label: "Doctor", type: "text", required: true },
      { key: "doctorBirthdate", label: "Doctor's birthdate", type: "date", hint: "Airlines ask for it." },
      { key: "repName", label: "Asked for by", type: "text", required: true, hint: "The medical sales associate." },
      { key: "requestedOn", label: "Asked for on", type: "date" },
      { key: "kind", label: "What", type: "choice", options: TRAVEL_KIND, required: true },
      { key: "status", label: "Status", type: "choice", options: TRAVEL_STATUS, required: true },
      { key: "travelDates", label: "Dates", type: "text", placeholder: "November 25-27, 2026", hint: "As agreed: check-in to check-out, or the flight dates." },
      { key: "startsOn", label: "First day", type: "date", hint: "For the countdown." },
      { key: "hotelOrFlight", label: "Hotel or airline", type: "text", wide: true, placeholder: "Edsa Shangri-La" },
      { key: "approvedOn", label: "Approved on", type: "date" },
      { key: "nextStep", label: "Next step", type: "text", placeholder: "For confirmation" },
      { key: "notes", label: "Notes", type: "long", wide: true },
    ],
    name: (i) => s(i.doctorName),
    columns: [
      { key: "name", label: "Doctor", cell: (i) => ({ type: "who", name: s(i.doctorName), sub: i.doctorBirthdate ? `born ${day(i.doctorBirthdate)}` : null, filled: tripStatus(i).tone === "warn" }) },
      { key: "what", label: "What", cell: (i) => ({ type: "tag", text: TRAVEL_KIND[i.kind as keyof typeof TRAVEL_KIND] ?? s(i.kind), tone: "outline" }) },
      { key: "when", label: "When", cell: (i) => ({ type: "text", text: s(i.travelDates) || "No dates yet", sub: tripStatus(i).text === "Took place" ? "took place" : typeof i.daysRemaining === "number" ? (i.daysRemaining === 0 ? "today" : `in ${i.daysRemaining} days`) : null }) },
      { key: "where", label: "Hotel or airline", kind: "hide-sm", cell: (i) => ({ type: "text", text: s(i.hotelOrFlight) || null }) },
      { key: "rep", label: "Asked by", kind: "hide-sm", cell: (i) => ({ type: "text", text: s(i.repName) }) },
      { key: "status", label: "Status", cell: (i) => ({ type: "tag", ...tripStatus(i), dot: true }) },
    ],
    filter: {
      label: "Show",
      options: { coming: "Coming up", waiting: "Waiting", past: "Took place" },
      matches: (i, key) => {
        const past = typeof i.daysRemaining === "number" && i.daysRemaining < 0;
        return key === "past" ? past && i.status !== "cancelled" : key === "waiting" ? i.status === "for_approval" || i.status === "for_processing" : !past && i.status !== "cancelled";
      },
    },
    search: (i) => [i.doctorName, i.repName, i.hotelOrFlight, i.travelDates].map(s).join(" "),
    subline: (i) => [TRAVEL_KIND[i.kind as keyof typeof TRAVEL_KIND], i.travelDates, i.repName ? `asked for by ${i.repName}` : null].filter(Boolean).map(s).join(" · "),
    status: (i) => tripStatus(i),
    facts: (i) => [
      { label: "When", value: s(i.travelDates) || "No dates yet" },
      { label: "Hotel or airline", value: s(i.hotelOrFlight) || "—" },
      { label: "Approved", value: day(i.approvedOn) ?? "Not yet" },
      { label: "Next step", value: s(i.nextStep) || "—" },
    ],
    steps: [
      { action: "approved", label: "Approve", primary: (i) => i.status === "for_approval" },
      { action: "for_processing", label: "For processing" },
      { action: "booked", label: "Mark booked", primary: (i) => i.status === "approved" || i.status === "for_processing" },
      { action: "cancelled", label: "Cancel" },
    ],
    details: (i) => [
      { title: "The doctor", rows: [{ label: "Doctor", value: s(i.doctorName) }, { label: "Birthdate", value: day(i.doctorBirthdate) }] },
      { title: "The request", rows: [{ label: "Asked for by", value: s(i.repName) }, { label: "Asked for on", value: day(i.requestedOn) }, { label: "First day", value: day(i.startsOn) }] },
      { title: "Notes", rows: [{ label: "Notes", value: s(i.notes) || null }] },
    ],
  },
  devices: {
    path: "devices",
    route: "/devices",
    area: "devices",
    title: "Devices issued",
    icon: "devices",
    intro: "Laptops, phones and SIMs handed to people",
    one: "device issue",
    fields: [
      { key: "issuedTo", label: "Given to", type: "text", required: true, wide: true, placeholder: "Angelica Saludes" },
      { key: "issuedOn", label: "Given on", type: "date" },
      { key: "condition", label: "Condition", type: "choice", options: CONDITION, required: true },
      { key: "laptop", label: "Laptop or tablet", type: "text", placeholder: "HP laptop" },
      { key: "phone", label: "Phone", type: "text", placeholder: "Galaxy A06 5G" },
      { key: "sim", label: "SIM", type: "text", placeholder: "DITO" },
      { key: "signedBy", label: "Signed by", type: "text" },
      { key: "notes", label: "Notes", type: "long", wide: true },
    ],
    name: (i) => s(i.issuedTo),
    columns: [
      { key: "name", label: "Given to", cell: (i) => ({ type: "who", name: s(i.issuedTo), sub: s(i.signedBy) ? `signed by ${s(i.signedBy)}` : null }) },
      { key: "laptop", label: "Laptop or tablet", cell: (i) => ({ type: "text", text: s(i.laptop) || null }) },
      { key: "phone", label: "Phone", kind: "hide-sm", cell: (i) => ({ type: "text", text: s(i.phone) || null }) },
      { key: "sim", label: "SIM", kind: "hide-sm", cell: (i) => ({ type: "text", text: s(i.sim) || null }) },
      { key: "when", label: "Given on", cell: (i) => ({ type: "text", text: day(i.issuedOn) }) },
      { key: "condition", label: "Condition", kind: "hide-sm", cell: (i) => ({ type: "tag", text: CONDITION[i.condition as keyof typeof CONDITION] ?? s(i.condition), tone: i.condition === "brand_new" ? "good" : "mute" }) },
    ],
    filter: { label: "Show", options: { laptop: "Laptops", phone: "Phones", sim: "SIMs" }, matches: (i, key) => Boolean(i[key]) },
    search: (i) => [i.issuedTo, i.laptop, i.phone, i.sim, i.signedBy].map(s).join(" "),
    subline: (i) => [day(i.issuedOn) ? `given ${day(i.issuedOn)}` : null, i.signedBy ? `signed by ${i.signedBy}` : null].filter(Boolean).map(s).join(" · "),
    status: (i) => ({ text: CONDITION[i.condition as keyof typeof CONDITION] ?? s(i.condition), tone: i.condition === "brand_new" ? "good" : "mute" }),
    facts: (i) => [
      { label: "Laptop or tablet", value: s(i.laptop) || "—" },
      { label: "Phone", value: s(i.phone) || "—" },
      { label: "SIM", value: s(i.sim) || "—" },
      { label: "Given on", value: day(i.issuedOn) ?? "—" },
    ],
    steps: [],
    details: (i) => [{ title: "The hand-over", rows: [{ label: "Given to", value: s(i.issuedTo) }, { label: "Signed by", value: s(i.signedBy) || null }, { label: "Notes", value: s(i.notes) || null }] }],
  },
};
