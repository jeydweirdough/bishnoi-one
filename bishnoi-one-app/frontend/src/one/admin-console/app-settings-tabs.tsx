"use client";

import { usePathname } from "next/navigation";
import { currentOf } from "@/src/platform/shell/sidebar";
import { LinkTabs, type LinkTab } from "@/src/platform/ui/link-tabs";

/** An app's settings tabs with a second row: the tab you're on shows its pages under it (the CRM's, 2026-11-01). */
export function GroupedTabs({ label, groups }: { label: string; groups: { label: string; pages: LinkTab[]; top: LinkTab }[] }) {
  const pathname = usePathname();
  const top = currentOf(groups.map((g) => g.top), pathname, null);
  const open = groups.find((g) => g.top === top);
  return (
    <>
      <LinkTabs label={label} tabs={groups.map((g) => g.top)} />
      {open && <LinkTabs sub label={open.label} tabs={open.pages} />}
    </>
  );
}
