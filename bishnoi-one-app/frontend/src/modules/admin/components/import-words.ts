import type { ImportKind } from "@/src/modules/admin/actions/imports";

/** What each import is called, where it goes back to, and how rows are matched. */
export const IMPORTS: Record<ImportKind, { one: string; many: string; back: string; match: string }> = {
  permits: {
    one: "permit",
    many: "permits",
    back: "/admin/permits",
    match: "A permit already here with the same reference number is updated; the rest are added.",
  },
  expatriates: {
    one: "expatriate document",
    many: "expatriate documents",
    back: "/admin/immigration",
    match: "A document already here with the same document number is updated; the rest are added.",
  },
  documents: {
    one: "document",
    many: "documents",
    back: "/admin/documents",
    match: "A document already here with the same reference number (or, without one, the same title and counterparty) is updated; the rest are added.",
  },
  properties: {
    one: "property",
    many: "properties",
    back: "/admin/properties",
    match: "A property already here with the same name is updated; the rest are added.",
  },
};
