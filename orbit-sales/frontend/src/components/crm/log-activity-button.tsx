"use client";

import { NotebookPen, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useRef } from "react";
import { Button } from "@/src/platform/ui/button";
import type { Assignable, Org, Ref } from "@/src/platform/lib/types";
import { LogActivity } from "./log-activity";

/** "Log activity": a button that opens the form in a panel, so a page isn't
 *  half form before anyone has anything to log. */
export function LogActivityButton({
  variant = "default",
  label = "Log activity",
  ...form
}: {
  variant?: "primary" | "default";
  label?: string;
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
      <Button variant={variant} icon={<NotebookPen className="size-4" aria-hidden />} onClick={() => dialog.current?.showModal()}>
        {label}
      </Button>
      <dialog ref={dialog} aria-labelledby={titleId} className="m-auto w-[min(36rem,calc(100vw-2rem))] rounded-[3px] bg-sheet p-0 text-ink shadow-overlay backdrop:bg-ink/30">
        <div className="flex items-center justify-between border-b border-rule px-5 py-3">
          <h2 id={titleId} className="text-heading">
            Log activity
          </h2>
          <button type="button" onClick={() => dialog.current?.close()} className="rounded-[3px] p-1 text-ink-3 hover:bg-bench hover:text-ink" aria-label="Close">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="max-h-[75vh] overflow-y-auto px-5 pt-4 pb-5">
          <LogActivity
            {...form}
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
