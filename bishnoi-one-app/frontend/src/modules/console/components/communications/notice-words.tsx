import { Flag } from "@/src/modules/console/platform/ui/marks";
import { NOTICE_STATES, when } from "@/src/modules/console/lib/words";
import type { Notice, NoticeLevel, NoticeState } from "@/src/modules/console/lib/types";

// How a notice is marked wherever it shows: its level, its state, who it is
// for and when. Words first; the borders only back them up.

export const NOTICE_LEVELS: Record<NoticeLevel, string> = { info: "Info", warning: "Warning", critical: "Critical" };

export function NoticeLevelMark({ level }: { level: NoticeLevel }) {
  if (level === "critical") return <Flag letter="!">{NOTICE_LEVELS.critical}</Flag>;
  return (
    <span
      className={`inline-flex h-5 items-center rounded-full px-1.5 text-stamp uppercase ${
        level === "warning" ? "border border-ink bg-ink text-white" : "border border-rule-strong text-ink-3"
      }`}
    >
      {NOTICE_LEVELS[level]}
    </span>
  );
}

// Showing is the one people see now, so it is the solid one; a draft is dashed
// (not out yet); ended is quiet.
const STATE_STYLE: Record<NoticeState, string> = {
  draft: "border border-dashed border-ink-2 text-ink-2",
  scheduled: "border border-ink-2 text-ink-2",
  showing: "border border-hema bg-hema text-white",
  ended: "text-ink-3",
};

export function NoticeStateMark({ state }: { state: NoticeState }) {
  return (
    <span className={`inline-flex h-5 items-center rounded-full px-1.5 text-stamp whitespace-nowrap uppercase ${STATE_STYLE[state]}`}>
      {NOTICE_STATES[state]}
    </span>
  );
}

/** Who sees it: everyone, one company, one application's users, or both. */
export function audience(n: Pick<Notice, "company" | "application">): string {
  if (n.company && n.application) return `${n.company.name}'s users of ${n.application.name}`;
  if (n.company) return `Everyone at ${n.company.name}`;
  if (n.application) return `Everyone using ${n.application.name}`;
  return "Everyone";
}

/** When it shows: "Sep 24, 2026, 10:00 AM – Sep 24, 2026, 12:00 PM", or open-ended. */
export function noticeWindow(n: Pick<Notice, "startsAt" | "endsAt">, zone?: string): string {
  return n.endsAt ? `${when(n.startsAt, zone)} – ${when(n.endsAt, zone)}` : `From ${when(n.startsAt, zone)}, until withdrawn`;
}
