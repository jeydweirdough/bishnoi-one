"use client";

import { NotebookPen } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { QuickAction, buttonClass } from "@/src/platform/ui/button";
import type { CrmKind, Assignable, Org, Ref } from "@/src/platform/lib/types";

/** "Log activity": opens the Log activity page (/activities/new) with what's
 *  known already (the kind, the customer or contact), and comes back here once
 *  it's saved. The form props are kept for the callers; the page loads its own. */
export function LogActivityButton({
  variant = "default",
  label = "Log activity",
  kind,
  quick,
  companyId,
  contactId,
}: {
  variant?: "primary" | "default";
  label?: string;
  /** Opens on this kind of activity. */
  kind?: CrmKind;
  /** Drawn as a small pill, icon and name (the customer page's quick actions). */
  quick?: ReactNode;
  org?: Org;
  now?: string;
  people?: Assignable[];
  companyId?: string;
  contactId?: string;
  contacts?: Ref[];
  companies?: Ref[];
}) {
  const path = usePathname();
  const search = useSearchParams();
  const here = `${path}${search.size ? `?${search}` : ""}`;
  const q = new URLSearchParams({ back: here });
  if (kind) q.set("kind", kind);
  if (companyId) q.set("company", companyId);
  if (contactId) q.set("contact", contactId);
  const href = `/activities/new?${q}`;
  return quick ? (
    <QuickAction href={href} icon={quick}>
      {label}
    </QuickAction>
  ) : (
    <Link href={href} className={buttonClass(variant)}>
      <NotebookPen className="size-4" aria-hidden />
      {label}
    </Link>
  );
}
