import { AlarmClock, Check, Hourglass, PackageMinus } from "lucide-react";
import type { Material, MaterialStatus, Urgency } from "@/src/actions/materials";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { day } from "@/src/components/operations/kinds";

// Urgency, the honest way: only from the material's own date needed, how long
// it has waited on someone, and the stock left. No timer that resets, no
// scarcity that isn't there: if nothing is pressing, nothing says so.

const TONE: Record<Urgency["tier"], string> = {
  overdue: "border-danger bg-danger-tint text-danger",
  urgent: "border-[#e0a43a] bg-[#fbf0d9] text-[#8a5a00]",
  approaching: "border-[#e0a43a] bg-[#fbf0d9] text-[#8a5a00]",
  upcoming: "border-rule-strong bg-sheet text-ink",
  good_standing: "border-rule-strong bg-sheet text-ink",
  none: "border-rule-strong bg-sheet text-ink",
};

/** Under the material's name: the step that moves it on, and why it's pressing now. */
export function UrgencyBanner({ material: m }: { material: Material }) {
  const u = m.urgency;
  if (!u.next) return null;
  const pressing = u.tier === "overdue" || u.tier === "urgent" || u.tier === "approaching";
  const Icon = u.lowStock ? PackageMinus : u.waiting && u.waiting.days >= 3 ? Hourglass : AlarmClock;
  return (
    <div role={pressing ? "alert" : "note"} className={`mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[16px] border px-4 py-3 ${TONE[u.tier]}`}>
      <Icon className="size-5 shrink-0" aria-hidden />
      <p className="min-w-0 flex-1 text-[14px] font-medium">{u.next}</p>
      {u.neededIn !== null && m.neededBy && (
        <span className="flex items-center gap-2 text-[13px]">
          Needed by {day(m.neededBy)}
          <CountdownBadge daysRemaining={u.neededIn} />
        </span>
      )}
    </div>
  );
}

/** In the list: when it's needed, counting down until it's in stock. */
export function NeededCell({ material: m }: { material: Material }) {
  const u = m.urgency;
  if (u.neededIn !== null) return <CountdownBadge daysRemaining={u.neededIn} compact />;
  if (u.lowStock) return <span className="text-meta font-semibold text-[#8a5a00]">Only {m.available.toLocaleString()} free</span>;
  if (m.neededBy && (m.status === "available" || m.status === "retired")) return <span className="text-meta text-ink-3">In stock</span>;
  return <span className="text-meta text-ink-3">No date set</span>;
}

/** How long it has waited, when that's worth a follow-up. */
export function waitingWords(u: Urgency): string | null {
  if (!u.waiting || u.waiting.days < 3) return null;
  return `Waiting ${u.waiting.days} days on the ${u.waiting.on}`;
}

const STAGES: { label: string; reached: MaterialStatus[] }[] = [
  { label: "Design", reached: ["draft", "returned", "pharmacy_review", "approved", "in_production", "available", "retired"] },
  { label: "Pharmacy review", reached: ["pharmacy_review", "approved", "in_production", "available", "retired"] },
  { label: "Production", reached: ["approved", "in_production", "available", "retired"] },
  { label: "In stock", reached: ["available", "retired"] },
  { label: "Distribution", reached: ["available", "retired"] },
];

/** Where it is on the way from design to the teams: done, here, still to come. */
export function StageTracker({ material: m, distributed }: { material: Material; distributed: boolean }) {
  if (m.status === "rejected") return null;
  const reached = STAGES.map((s) => s.reached.includes(m.status));
  // The last stage reached is where it is now; distribution is done once some has gone out.
  const here = reached.lastIndexOf(true);
  return (
    <ol className="mt-4 grid grid-cols-5 gap-1.5" aria-label="Stages">
      {STAGES.map((s, n) => {
        const done = n < here || (n === here && n === STAGES.length - 1 && distributed);
        const current = n === here && !done;
        return (
          <li key={s.label} className="min-w-0" aria-current={current ? "step" : undefined}>
            <span className={`block h-1.5 rounded-full ${done ? "bg-ink" : current ? "bg-[#e0a43a]" : "bg-rule"}`} aria-hidden />
            <span className={`mt-1.5 flex items-center gap-1 truncate text-[12px] ${current ? "font-semibold text-ink" : done ? "text-ink-2" : "text-ink-3"}`}>
              {done && <Check className="size-3 shrink-0" aria-hidden />}
              {s.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
