import type { Format } from "@/src/platform/lib/format";
import type { KpiStatus, KpiUnit } from "@/src/platform/lib/types";

/** A KPI value as people read it: pesos, a percentage, or a count. */
export function kpiValue(unit: KpiUnit, value: number | null | undefined, fmt: Format): string {
  if (value === null || value === undefined) return "—";
  if (unit === "money") return fmt.peso(value);
  if (unit === "percent") return `${value}%`;
  return value.toLocaleString("en-PH");
}

/** A target as typed in a box: pesos for money, else a whole number. */
export function kpiText(unit: KpiUnit, value: number | undefined, fmt: Format): string {
  if (value === undefined) return "";
  return unit === "money" ? fmt.pesosText(value) : String(value);
}

/** A box's text as a value: null for empty, undefined when it isn't one. */
export function kpiParse(unit: KpiUnit, text: string, fmt: Format): number | null | undefined {
  const t = text.trim();
  if (!t) return null;
  if (unit === "money") return fmt.toCentavos(t) ?? undefined;
  const n = Number(t.replace(/,/g, ""));
  if (!Number.isInteger(n) || n < 0 || (unit === "percent" && n > 100)) return undefined;
  return n;
}

export const UNIT_LABELS: Record<KpiUnit, string> = { count: "A count", money: "An amount (₱)", percent: "A percentage" };

export const STATUS: Record<KpiStatus, { label: string; text: string; fill: string }> = {
  green: { label: "On target", text: "text-filed", fill: "bg-filed" },
  amber: { label: "Slightly behind", text: "text-due-today", fill: "bg-due-today" },
  red: { label: "Behind", text: "text-danger", fill: "bg-danger" },
  waiting: { label: "No result yet", text: "text-ink-3", fill: "bg-rule-strong" },
  none: { label: "No target", text: "text-ink-3", fill: "bg-rule-strong" },
};

export const FILTER_WORDS: Record<string, string> = {
  kind: "Only one kind of activity",
  outcome: "Only one visit outcome",
  productId: "Only one product",
};

export const words = (code: string) => code.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
