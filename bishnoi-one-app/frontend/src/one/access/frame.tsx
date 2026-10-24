import type { ReactNode } from "react";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { loadAccess } from "./load";

const TABS = [
  { value: "people", label: "People", href: "/platform/access" },
  { value: "roles", label: "Roles", href: "/platform/access/roles" },
];

/**
 * Access in one place (decided 2026-10-23): who may open which module, and what
 * they may do there, for the whole company. Only its administrators see it.
 */
export async function AccessFrame({ current, children }: { current: "people" | "roles"; children: ReactNode }) {
  const data = await loadAccess();
  return (
    <main className="mx-auto max-w-[80rem] px-4 pt-6 pb-12 sm:px-6 lg:px-8">
      <PageHeader title="People and access" actions={data ? <ToggleLinks options={TABS} current={current} /> : undefined}>
        {data ? (
          <>
            Each person at {data.company.name} has one role, for every module: what they may do in each, and whose records it reaches.
            The modules are told at once.
          </>
        ) : null}
      </PageHeader>
      {data ? (
        children
      ) : (
        <Sheet>
          <Empty icon="roles" title="No access to people and access">
            Only your company&apos;s administrators manage who may do what. Ask one of them if something needs to change.
          </Empty>
        </Sheet>
      )}
    </main>
  );
}
