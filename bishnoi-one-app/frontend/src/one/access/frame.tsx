import type { ReactNode } from "react";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { loadAccess } from "./load";
import { ROLE_ACTIONS } from "./labels";

// Plain strings: they sit behind the title's ⓘ, so the page starts with its work (2026-11-01).
const INTRO = {
  people: "Add employees, give them apps and a role in each, set passwords and switch them off. The apps are told at once.",
  bin: "Deleted employees can't sign in, and what they did stays. Restore puts them back switched off; Delete permanently removes them for good.",
  roles: "What each role can do, in plain words, and whose records it sees. Start from one of Bishnoi One's job roles and adjust it. Every app is told at once.",
};

/**
 * Roles and permissions in the Admin Console (decided 2026-10-23, framed in the
 * console 2026-10-24): what each role may do in each module, and who holds
 * which, for the whole company. Only its administrators see it.
 */
export async function AccessFrame({ current, children }: { current: "people" | "roles" | "bin"; children: ReactNode }) {
  const data = await loadAccess();
  return (
    <>
      <PageHeader title={current === "people" ? "Employees" : current === "bin" ? "Recycle bin" : "Roles"} crumbs={current === "bin" ? [{ href: "/platform/roles/people", label: "Employees" }] : undefined} actions={current === "roles" && data ? <div id={ROLE_ACTIONS} className="flex flex-wrap items-center gap-2" /> : undefined}>
        {data ? INTRO[current] : null}
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
