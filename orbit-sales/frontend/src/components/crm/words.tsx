import type { IconName } from "@/src/platform/ui/icons";
import type { CompanyStatus, CrmKind } from "@/src/platform/lib/types";

export const KINDS: { kind: CrmKind; label: string; icon: IconName; planned: boolean }[] = [
  { kind: "call", label: "Call", icon: "call", planned: false },
  { kind: "meeting", label: "Meeting", icon: "calendar", planned: true },
  { kind: "email", label: "Email", icon: "email", planned: false },
  { kind: "note", label: "Note", icon: "note", planned: false },
  { kind: "task", label: "Task", icon: "task", planned: true },
];

export const kindOf = (kind: CrmKind) => KINDS.find((k) => k.kind === kind) ?? KINDS[0];

export const STATUSES: { value: CompanyStatus; label: string }[] = [
  { value: "prospect", label: "Prospect" },
  { value: "customer", label: "Customer" },
  { value: "partner", label: "Partner" },
  { value: "inactive", label: "Inactive" },
];

const STATUS_STYLE: Record<CompanyStatus, string> = {
  prospect: "border-rule-strong text-ink-2",
  customer: "border-hema bg-hema-tint text-hema",
  partner: "border-filed text-filed",
  inactive: "border-rule text-ink-3",
};

export function StatusTag({ status }: { status: CompanyStatus }) {
  const label = STATUSES.find((s) => s.value === status)?.label ?? status;
  return (
    <span className={`inline-flex h-5 items-center rounded-[2px] border px-1.5 text-stamp uppercase ${STATUS_STYLE[status]}`}>{label}</span>
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
