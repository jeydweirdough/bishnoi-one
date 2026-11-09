"use client";

import { usePathname } from "next/navigation";
import { UnderlineTabs } from "@/src/platform/ui/list-layout";
import { sectionAt, type Section } from "./sections";

/**
 * The tabs of the area this page belongs to (sections.ts), above the page: Bills, Payment vouchers, Supplier
 * aging and Suppliers under Payables, and so on. Only on the area's own pages, not on a record or form inside
 * one, and only the tabs this person may open (the shell passes those, worked out on the server).
 */
export function SectionTabs({ sections }: { sections: Section[] }) {
  const pathname = usePathname();
  const section = sectionAt(sections, pathname);
  if (!section || section.tabs.length < 2) return null;
  return (
    // The tabs carry their own side padding; pull them out to the page's edges so they line up with the page.
    // On a phone they swipe sideways with no scrollbar showing (the user's preference, as on Overview's tabs).
    <div className="-mx-4 mb-4 sm:-mx-5 print:hidden [&>nav]:[scrollbar-width:none] [&>nav::-webkit-scrollbar]:hidden">
      <UnderlineTabs label={section.label} tabs={section.tabs.map((t) => ({ href: t.href, label: t.label, current: t.href === pathname }))} />
    </div>
  );
}
