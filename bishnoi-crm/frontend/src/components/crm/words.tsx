import type { IconName } from "@/src/platform/ui/icons";
import type { CompanyStatus, CrmKind, CustomerType, CustomerTypeColor } from "@/src/platform/lib/types";

export const KINDS: { kind: CrmKind; label: string; icon: IconName; planned: boolean }[] = [
  { kind: "call", label: "Call", icon: "call", planned: false },
  { kind: "meeting", label: "Meeting", icon: "calendar", planned: true },
  { kind: "email", label: "Email", icon: "email", planned: false },
  { kind: "note", label: "Note", icon: "note", planned: false },
  { kind: "task", label: "Task", icon: "task", planned: true },
];

export const kindOf = (kind: CrmKind) => KINDS.find((k) => k.kind === kind) ?? KINDS[0];

export const TYPE_COLORS: Record<CustomerTypeColor, { label: string; style: string }> = {
  gray: { label: "Gray", style: "border-transparent bg-[#f0f0ee] text-ink-2" },
  brand: { label: "Ink", style: "border-ink bg-sheet text-ink" },
  green: { label: "Green", style: "border-transparent bg-[#e6f2e1] text-[#3f6f35]" },
  blue: { label: "Blue", style: "border-transparent bg-[#e7eef8] text-[#1f4f8a]" },
  amber: { label: "Amber", style: "border-transparent bg-[#fbf0d9] text-[#8a5a00]" },
  red: { label: "Red", style: "border-transparent bg-danger-tint text-danger" },
  purple: { label: "Purple", style: "border-transparent bg-[#f1eaf8] text-[#5b3a8a]" },
  muted: { label: "Faded", style: "border-dashed border-rule-strong text-ink-3" },
};

/** The customer types to pick from: those switched on, plus the one a company already has. */
export const typeOptions = (types: CustomerType[], current?: string) =>
  types.filter((t) => t.isActive || t.code === current).map((t) => ({ value: t.code, label: t.name }));

export function StatusTag({ status, types }: { status: CompanyStatus; types: CustomerType[] }) {
  const type = types.find((t) => t.code === status);
  return (
    <span className={`inline-flex h-6 items-center rounded-md border px-2.5 text-meta font-medium whitespace-nowrap ${TYPE_COLORS[type?.color ?? "gray"].style}`}>
      {type?.name ?? status}
    </span>
  );
}

/**
 * A moment as a datetime field wants it ("2026-09-24T14:00"), in the company's
 * own timezone, so what the field shows is what the company's clocks say.
 */
export function localDateTime(moment: Date, timeZone: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(moment)
      .map((p) => [p.type, p.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

/** Tomorrow at 9 in the morning, where the company is: a sensible time to plan for. */
export function tomorrowMorning(timeZone: string): string {
  return `${localDateTime(new Date(Date.now() + 24 * 3600 * 1000), timeZone).slice(0, 10)}T09:00`;
}

/** The part of a website to show: "acme.com", not "https://www.acme.com/". */
export const siteLabel = (url: string) => url.replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/$/, "");
export const siteHref = (url: string) => (/^https?:\/\//.test(url) ? url : `https://${url}`);
