"use client";

import { Check, Trophy, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { toast } from "sonner";
import { moveDealStage } from "@/src/modules/crm/actions/deals";
import type { DealStage, DealState } from "@/src/platform/lib/types";

// The deal's stages as the UI kit's stage track (decided 2026-10-22): one arrow
// per open stage, the ones behind it tinted, the one it's at filled, the ones
// ahead plain. Clicking a stage moves the deal there (the same step as the
// board's drag). Winning or losing it stays with Mark won and Mark lost below, which
// asks for the quote or the reason.

/** The pipeline's blues, light to dark as stages get likelier (as on the deals board). */
const BLUES = ["#9ec5f4", "#7fb0ec", "#5598e7", "#2f7fd8", "#1c5cab"];

function colourOf(i: number, of: number): string {
  if (of <= 1) return BLUES[BLUES.length - 1];
  return BLUES[Math.round((i / (of - 1)) * (BLUES.length - 1))];
}

export function StageTrack({
  dealId,
  current,
  state,
  stages,
  canMove,
}: {
  dealId: string;
  current: string;
  state: DealState;
  stages: DealStage[];
  canMove: boolean;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const open = stages.filter((s) => s.outcome === "open" && s.isActive).sort((a, b) => a.sortOrder - b.sortOrder);
  const at = state === "open" ? open.findIndex((s) => s.code === current) : open.length;

  function move(s: DealStage) {
    if (!canMove || state !== "open" || s.code === current || pending) return;
    start(async () => {
      const r = await moveDealStage(dealId, s.code);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`Moved to ${s.name}`);
      router.refresh();
    });
  }

  if (open.length === 0) return null;
  return (
    <div className="mt-3">
      <div role="group" aria-label="Deal stage" className={`flex w-full max-w-[44rem] overflow-hidden rounded-[12px] border border-rule bg-sheet ${pending ? "opacity-60" : ""}`}>
        {open.map((s, i) => {
          const c = colourOf(i, open.length);
          const past = i < at;
          const here = i === at;
          const first = i === 0;
          return (
            <button suppressHydrationWarning
              key={s.code}
              type="button"
              onClick={() => move(s)}
              disabled={!canMove || state !== "open"}
              aria-current={here ? "step" : undefined}
              aria-label={here ? `${s.name}, current stage` : canMove && state === "open" ? `Move to ${s.name}` : s.name}
              title={`${s.name} · ${s.probability}% likely`}
              style={{
                clipPath: first
                  ? "polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%)"
                  : "polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%, 12px 50%)",
                marginLeft: first ? 0 : -11,
                background: here ? c : past ? `color-mix(in srgb, ${c} 18%, #ffffff)` : undefined,
                color: here ? (i / Math.max(1, open.length - 1) > 0.45 ? "#ffffff" : "#141414") : past ? "#1c5cab" : undefined,
              }}
              className={`relative flex h-11 min-w-0 flex-1 items-center justify-center gap-1.5 text-[0.78125rem] font-medium whitespace-nowrap transition-colors ${
                first ? "pr-4 pl-3" : "pr-4 pl-6"
              } ${!here && !past ? "text-ink-3" : ""} ${canMove && state === "open" && !here ? "cursor-pointer hover:bg-[#f4f4f2] hover:text-ink" : "cursor-default"}`}
            >
              {past && <Check className="size-3.5 shrink-0" aria-hidden />}
              <span className="truncate">{s.name}</span>
            </button>
          );
        })}
        {state !== "open" && (
          <span
            className={`flex h-11 shrink-0 items-center gap-1.5 px-4 text-[0.78125rem] font-semibold whitespace-nowrap ${state === "won" ? "bg-[#e6f2e1] text-[#3f6f35]" : "bg-[#f4f4f2] text-ink-2"}`}
          >
            {state === "won" ? <Trophy className="size-3.5" aria-hidden /> : <XCircle className="size-3.5" aria-hidden />}
            {state === "won" ? "Won" : "Lost"}
          </span>
        )}
      </div>
      {canMove && state === "open" && <p className="mt-1.5 text-meta text-ink-3">Click a stage to move the deal there. To close it, use Mark won or Mark lost below.</p>}
    </div>
  );
}
