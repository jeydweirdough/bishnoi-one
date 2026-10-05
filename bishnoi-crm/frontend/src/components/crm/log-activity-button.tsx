"use client";

import { NotebookPen, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ReactNode, useId, useRef } from "react";
import { Button } from "@/src/platform/ui/button";
import type { CrmKind, Assignable, Org, Ref } from "@/src/platform/lib/types";
import { LogActivity } from "./log-activity";

/** "Log activity": a button that opens the form in a panel, so a page isn't
 *  half form before anyone has anything to log. */
export function LogActivityButton({
  variant = "default",
  label = "Log activity",
  kind,
  quick,
  ...form
}: {
  variant?: "primary" | "default";
  label?: string;
  /** Opens on this kind of activity. */
  kind?: CrmKind;
  /** Drawn as a round icon with its name under it (the customer page's quick actions). */
  quick?: ReactNode;
  org: Org;
  now: string;
  people: Assignable[];
  companyId?: string;
  contactId?: string;
  contacts?: Ref[];
  companies?: Ref[];
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const router = useRouter();
  const titleId = useId();
  return (
    <>
      {quick ? (
        <button type="button" onClick={() => dialog.current?.showModal()} className="group flex w-14 flex-col items-center gap-1 text-meta text-ink-2 hover:text-ink">
          <span className="grid size-10 place-items-center rounded-full border border-rule bg-sheet group-hover:border-ink-3">{quick}</span>
          {label}
        </button>
      ) : (
        <Button variant={variant} icon={<NotebookPen className="size-4" aria-hidden />} onClick={() => dialog.current?.showModal()}>
          {label}
        </Button>
      )}
      <dialog ref={dialog} aria-labelledby={titleId} className="m-auto w-[min(36rem,calc(100vw-2rem))] rounded-[6px] bg-sheet p-0 text-ink shadow-overlay backdrop:bg-ink/30">
        <div className="flex items-center justify-between border-b border-rule px-5 py-3">
          <h2 id={titleId} className="text-heading">
            Log activity
          </h2>
          <button type="button" onClick={() => dialog.current?.close()} className="rounded-[6px] p-1 text-ink-3 hover:bg-bench hover:text-ink" aria-label="Close">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="max-h-[75vh] overflow-y-auto px-5 pt-4 pb-5">
          <LogActivity
            {...form}
            initialKind={kind}
            onDone={() => {
              dialog.current?.close();
              router.refresh();
            }}
          />
        </div>
      </dialog>
    </>
  );
}
