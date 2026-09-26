"use client";

import { Printer } from "lucide-react";
import { useEffect } from "react";
import { Button } from "@/src/platform/ui/button";

/** Prints the page; with `auto`, opens the print dialog once on arrival. */
export function PrintButton({ auto = false }: { auto?: boolean }) {
  useEffect(() => {
    if (!auto) return;
    const t = setTimeout(() => window.print(), 400);
    return () => clearTimeout(t);
  }, [auto]);
  return (
    <Button variant="primary" onClick={() => window.print()} icon={<Printer className="size-4" aria-hidden />}>
      Print
    </Button>
  );
}
