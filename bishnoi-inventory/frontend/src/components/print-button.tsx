"use client";

import { Printer } from "lucide-react";
import { useEffect } from "react";
import { Button, LinkButton } from "@/src/platform/ui/button";

/** On a record's page: opens its document to print or save as PDF. */
export function PrintLink({ href }: { href: string }) {
  return (
    <LinkButton href={href} icon={<Printer className="size-4" aria-hidden />} prefetch={false}>
      Print
    </LinkButton>
  );
}

/** Prints the page; the browser's print dialog also saves it as PDF. With
 *  `auto`, opens the dialog once on arrival. As the CRM's quotation does. */
export function PrintButton({ auto = false }: { auto?: boolean }) {
  useEffect(() => {
    if (!auto) return;
    const t = setTimeout(() => window.print(), 400);
    return () => clearTimeout(t);
  }, [auto]);
  return (
    <Button variant="primary" onClick={() => window.print()} icon={<Printer className="size-4" aria-hidden />}>
      Print or save as PDF
    </Button>
  );
}
