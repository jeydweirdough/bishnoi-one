"use client";

import { Mail } from "lucide-react";
import { useState } from "react";
import { Composer } from "./composer";

/** The customer page's Email: the composer, already about this customer. */
export function EmailButton({ companyId, companyName }: { companyId: string; companyName: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="group flex w-14 flex-col items-center gap-1 text-meta text-ink-2 hover:text-ink">
        <span className="grid size-10 place-items-center rounded-full border border-rule bg-sheet group-hover:border-ink-3">
          <Mail className="size-4" aria-hidden />
        </span>
        Email
      </button>
      <Composer open={open} onClose={() => setOpen(false)} customer={{ id: companyId, name: companyName }} />
    </>
  );
}
