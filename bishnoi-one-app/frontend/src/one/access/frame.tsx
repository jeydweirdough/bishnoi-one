import type { ReactNode } from "react";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { loadAccess } from "./load";

/**
 * Roles and permissions in the Admin Console (decided 2026-10-23, framed in the
 * console 2026-10-24): what each role may do in each module, and who holds
 * which, for the whole company. Only its administrators see it.
 */
export async function AccessFrame({ current, children }: { current: "people" | "roles" | "bin"; children: ReactNode }) {
  const data = await loadAccess();
  return (
    <>
      <PageHeader
        title={current === "people" ? "People" : current === "bin" ? "Recycle bin" : "Roles"}
        crumbs={current === "bin" ? [{ href: "/platform/roles/people", label: "People" }] : undefined}
      >
        {data ? (
          current === "bin" ? (
            <>People deleted from {data.company.name}. They can&apos;t sign in, and what they did stays. Restore puts them back on People, switched off until you switch them on.</>
          ) : current === "people" ? (
            <>Everyone at {data.company.name}, once for every module: add people, give each one role and the modules they may open, set passwords, switch people off. The modules are told at once.</>
          ) : (
            <>What each role can do, in plain words, and whose records it sees. Start from one of Bishnoi One&apos;s job roles and adjust it. Every app is told at once.</>
          )
        ) : null}
      </PageHeader>
      {data ? (
        children
      ) : (
        <Sheet>
          <Empty icon="roles" title="No access to roles and permissions">
            Only your company&apos;s administrators manage who may do what. Ask one of them if something needs to change.
          </Empty>
        </Sheet>
      )}
    </>
  );
}
