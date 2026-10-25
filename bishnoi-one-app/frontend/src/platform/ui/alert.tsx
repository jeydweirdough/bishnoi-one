import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from "lucide-react";
import type { ReactNode } from "react";

// Messages in the UI kit's look (decided 2026-10-22), one set for every app:
//  - Alert: a card on the page, with a round icon, a title, a line and its
//    actions (Review, or ✕ to close);
//  - Banner: a strip across the top of a page or card (maintenance tonight,
//    a sync that failed, with Retry);
//  - InlineMessage: a few words beside a field or a button ("Saved 10:24").
// Each says what it means in words; the colour only backs them up.
//
// Same file in every app's src/platform/ui/: copy it as it is.

export type Tone = "info" | "ok" | "warn" | "bad";

const TONE: Record<Tone, { icon: typeof Info; ring: string; text: string; fill: string; strip: string }> = {
  info: { icon: Info, ring: "bg-[#e9f0fb] text-[#1f4f8a]", text: "text-[#1f4f8a]", fill: "border-[#d5e2f5] bg-[#f4f8fd]", strip: "bg-[#e9f0fb] text-[#1f4f8a]" },
  ok: { icon: CircleCheck, ring: "bg-[#e6f2e1] text-[#3f6f35]", text: "text-[#3f6f35]", fill: "border-[#d3e6cd] bg-[#f1f7ee]", strip: "bg-[#e6f2e1] text-[#3f6f35]" },
  warn: { icon: TriangleAlert, ring: "bg-[#fbf0d9] text-[#8a5a00]", text: "text-[#8a5a00]", fill: "border-[#f1e0b8] bg-[#fdf8ec]", strip: "bg-[#fbf0d9] text-[#8a5a00]" },
  bad: { icon: CircleAlert, ring: "bg-danger-tint text-danger", text: "text-danger", fill: "border-[#f5cdc8] bg-[#fef4f3]", strip: "bg-danger-tint text-danger" },
};

/** A message card. `filled` tints the whole card (for news that matters, like a payment recorded). */
export function Alert({
  tone = "info",
  title,
  children,
  actions,
  onClose,
  filled = false,
  className = "",
}: {
  tone?: Tone;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  onClose?: () => void;
  filled?: boolean;
  className?: string;
}) {
  const t = TONE[tone];
  const Icon = t.icon;
  return (
    <div role={tone === "bad" || tone === "warn" ? "alert" : "status"} className={`flex gap-3 rounded-[10px] border px-3.5 py-3 text-[0.84375rem] ${filled ? t.fill : "border-rule bg-sheet"} ${className}`}>
      <span className={`grid size-[22px] shrink-0 place-items-center rounded-full ${t.ring}`} aria-hidden>
        <Icon className="size-[13px]" strokeWidth={2.25} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-ink">{title}</p>
        {children && <div className="mt-0.5 text-ink-2">{children}</div>}
      </div>
      {(actions || onClose) && (
        <div className="ml-auto flex shrink-0 items-start gap-1.5">
          {actions}
          {onClose && (
            <button suppressHydrationWarning type="button" onClick={onClose} aria-label="Dismiss" className="grid size-7 place-items-center rounded-md text-ink-3 hover:bg-[#f4f4f2] hover:text-ink">
              <X className="size-4" aria-hidden />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** A strip across a page or card: maintenance tonight, a failed sync with its Retry. */
export function Banner({ tone = "info", children, action, onClose, className = "" }: { tone?: Tone; children: ReactNode; action?: ReactNode; onClose?: () => void; className?: string }) {
  const t = TONE[tone];
  const Icon = t.icon;
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={`flex flex-wrap items-center gap-2.5 rounded-md px-3.5 py-2 text-[0.8125rem] ${t.strip} ${className}`}>
      <Icon className="size-[15px] shrink-0" aria-hidden />
      <span className="min-w-0 flex-1">{children}</span>
      {action && <span className="font-semibold underline-offset-[3px] [&_a]:underline">{action}</span>}
      {onClose && (
        <button suppressHydrationWarning type="button" onClick={onClose} aria-label="Dismiss" className="grid size-6 place-items-center rounded opacity-70 hover:opacity-100">
          <X className="size-3.5" aria-hidden />
        </button>
      )}
    </div>
  );
}

/** A few words beside a field or button, with a small mark: "TIN must have 12 digits", "Saved 10:24". */
export function InlineMessage({ tone = "info", children }: { tone?: Tone; children: ReactNode }) {
  const t = TONE[tone];
  const Icon = t.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 text-[0.8125rem] font-medium ${t.text}`}>
      <Icon className="size-3.5" aria-hidden />
      {children}
    </span>
  );
}
