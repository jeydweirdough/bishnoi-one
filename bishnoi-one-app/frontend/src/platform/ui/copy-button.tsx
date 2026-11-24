"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

/** A small Copy beside a phone number, email or code (the UI kit's contact card): copied, it ticks for a moment. */
export function CopyButton({ text, what }: { text: string; what: string }) {
  const [done, setDone] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      toast.success(`${what} copied`);
      window.setTimeout(() => setDone(false), 1500);
    } catch {
      toast.error("Couldn't copy: select it and copy it by hand.");
    }
  }
  return (
    <button suppressHydrationWarning type="button" onClick={copy} aria-label={`Copy ${what.toLowerCase()}`} title={`Copy ${what.toLowerCase()}`} className="grid size-7 shrink-0 place-items-center rounded-md text-ink-3 transition-colors hover:bg-muted hover:text-ink">
      {done ? <Check className="size-3.5 text-emerald-700 dark:text-emerald-400" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
    </button>
  );
}
