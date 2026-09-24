"use client";

import { Eye, LogOut } from "lucide-react";
import { useTransition } from "react";
import { leaveCompany } from "../actions/session";

/**
 * Says, on every page, that these are somebody else's screens.
 *
 * A Developer Admin looking through a person sees exactly what that person
 * sees — which is the whole point, and exactly why it has to be impossible to
 * forget. Nothing can be changed while it is up; the API refuses every write,
 * and this says so before anyone tries.
 */
export function ViewingBanner({ who, company }: { who: string; company: string }) {
  const [leaving, start] = useTransition();
  return (
    <div className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 bg-ink px-4 py-2 text-sheet sm:px-6">
      <p className="flex min-w-0 items-center gap-2 text-meta">
        <Eye className="size-4 shrink-0" aria-hidden />
        <span className="min-w-0">
          You&apos;re seeing Nabhi as <b className="font-semibold">{who}</b> in {company}.
          <span className="text-sheet/70"> Looking only — nothing here can be changed.</span>
        </span>
      </p>
      <button
        type="button"
        disabled={leaving}
        onClick={() => start(async () => void (await leaveCompany()))}
        className="inline-flex shrink-0 items-center gap-1.5 rounded-[3px] bg-sheet/15 px-2.5 py-1 text-meta font-semibold hover:bg-sheet/25 disabled:opacity-60"
      >
        <LogOut className="size-3.5" aria-hidden />
        {leaving ? "Leaving…" : "Leave"}
      </button>
    </div>
  );
}
