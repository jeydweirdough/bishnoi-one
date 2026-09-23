import type { ReactNode } from "react";
import type { Format } from "@/src/platform/lib/format";
import type { ExtraValues, FormFieldDef } from "@/src/platform/lib/types";

/** An added field's value as a person reads it. */
export function extraText(fmt: Format, field: FormFieldDef, value: ExtraValues[string] | undefined): string | null {
  if (value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0)) return null;
  if (Array.isArray(value)) return value.join(", ");
  if (field.type === "yes_no") return value ? "Yes" : "No";
  if (field.type === "date") return fmt.dateLabel(String(value));
  if (field.type === "money") return fmt.peso(Math.round(Number(value) * 100));
  if (field.type === "number") return Number(value).toLocaleString();
  return String(value);
}

/** Rows for a record's particulars: each added field that has a value. */
export function extraItems(fmt: Format, fields: FormFieldDef[], values: ExtraValues | undefined): [string, string | null][] {
  return fields
    .filter((f) => !f.standard)
    .map((f) => [f.label, extraText(fmt, f, values?.[f.key])] as [string, string | null])
    .filter(([, v]) => v !== null);
}

/**
 * A record's particulars in the form's order, with the names the admin gave
 * them (Settings → Forms). Hidden fields aren't on the layout, so they aren't
 * shown. `shown` draws a built-in field that needs more than its text (a link,
 * "You"); `skip` leaves out what the page already shows elsewhere.
 */
export function layoutItems(
  fmt: Format,
  fields: FormFieldDef[],
  record: { extra?: ExtraValues } & object,
  shown: Record<string, ReactNode> = {},
  skip: string[] = [],
): [string, ReactNode][] {
  const values = record as Record<string, unknown>;
  return fields
    .filter((f) => !skip.includes(f.key))
    .map((f): [string, ReactNode] => {
      if (f.key in shown) return [f.label, shown[f.key]];
      if (!f.standard) return [f.label, extraText(fmt, f, record.extra?.[f.key])];
      const v = values[f.key];
      return [f.label, v === null || v === undefined || v === "" ? null : String(v)];
    });
}
