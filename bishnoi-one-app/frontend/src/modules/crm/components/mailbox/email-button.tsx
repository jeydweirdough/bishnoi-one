"use client";

import { QuickAction } from "@/src/platform/ui/button";
import { Mail } from "lucide-react";
import { useState } from "react";
import { Composer } from "@/src/modules/crm/components/mailbox/composer";

/** The customer page's Email: the composer, already about this customer. */
export function EmailButton({ companyId, companyName }: { companyId: string; companyName: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <QuickAction onClick={() => setOpen(true)} >
        <span className="text-ink-3" aria-hidden>
          <Mail className="size-4" aria-hidden />
        </span>
        Email
      </QuickAction>
      <Composer open={open} onClose={() => setOpen(false)} customer={{ id: companyId, name: companyName }} />
    </>
  );
}
