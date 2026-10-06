"use client";

import { Mail } from "lucide-react";
import { useState } from "react";
import { Composer } from "./composer";

/** The customer page's Email: the composer, already about this customer. */
export function EmailButton({ companyId, companyName }: { companyId: string; companyName: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="inline-flex h-9 items-center gap-2 rounded-full border border-rule-strong bg-sheet px-3.5 text-sm text-ink-2 transition-colors hover:border-ink hover:bg-mint hover:text-ink">
        <span className="text-ink-3" aria-hidden>
          <Mail className="size-4" aria-hidden />
        </span>
        Email
      </button>
      <Composer open={open} onClose={() => setOpen(false)} customer={{ id: companyId, name: companyName }} />
    </>
  );
}
