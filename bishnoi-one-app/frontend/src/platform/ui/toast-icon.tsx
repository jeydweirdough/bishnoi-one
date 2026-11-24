import { Check, CircleAlert, Info, TriangleAlert } from "lucide-react";

// A toast's round icon, as the UI kit's (decided 2026-10-22). Same file in every app's src/platform/ui/.
const LOOK = {
  ok: { Icon: Check, cls: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" },
  info: { Icon: Info, cls: "bg-blue-500/10 text-blue-700 dark:text-blue-400" },
  warn: { Icon: TriangleAlert, cls: "bg-amber-500/10 text-amber-700 dark:text-amber-400" },
  bad: { Icon: CircleAlert, cls: "bg-danger-tint text-danger" },
} as const;

export function ToastIcon({ tone }: { tone: keyof typeof LOOK }) {
  const { Icon, cls } = LOOK[tone];
  return (
    <span className={`grid size-5 place-items-center rounded-full ${cls}`} aria-hidden>
      <Icon className="size-3" strokeWidth={2.5} />
    </span>
  );
}
