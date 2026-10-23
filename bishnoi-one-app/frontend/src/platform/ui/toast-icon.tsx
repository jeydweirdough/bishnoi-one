import { Check, CircleAlert, Info, TriangleAlert } from "lucide-react";

// A toast's round icon, as the UI kit's (decided 2026-10-22). Same file in every app's src/platform/ui/.
const LOOK = {
  ok: { Icon: Check, cls: "bg-[#e6f2e1] text-[#3f6f35]" },
  info: { Icon: Info, cls: "bg-[#e9f0fb] text-[#1f4f8a]" },
  warn: { Icon: TriangleAlert, cls: "bg-[#fbf0d9] text-[#8a5a00]" },
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
