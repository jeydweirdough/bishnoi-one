"use client";

import { Printer } from "lucide-react";
import { Button } from "@/src/platform/ui/button";

/** Prints the page; the browser's print dialog also saves it as PDF. */
export function PrintButton() {
  return (
    <Button variant="primary" onClick={() => window.print()} icon={<Printer className="size-4" aria-hidden />}>
      Print or save as PDF
    </Button>
  );
}
