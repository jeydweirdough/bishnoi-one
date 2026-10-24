"use client";

import { Printer } from "lucide-react";
import { useEffect } from "react";
import { Button } from "@/src/platform/ui/button";

/** Prints the page (or a quotation written as code, which sits in a frame of its
 *  own); with `auto`, opens the print dialog once on arrival. */
function print() {
  const frame = document.querySelector<HTMLIFrameElement>("iframe[data-print]");
  (frame?.contentWindow ?? window).print();
}

export function PrintButton({ auto = false }: { auto?: boolean }) {
  useEffect(() => {
    if (!auto) return;
    const t = setTimeout(print, 400);
    return () => clearTimeout(t);
  }, [auto]);
  return (
    <Button variant="primary" onClick={print} icon={<Printer className="size-4" aria-hidden />}>
      Print
    </Button>
  );
}
