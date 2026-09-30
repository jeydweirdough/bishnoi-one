// The signed-in frame: the sidebar, and the banner when somebody is being
// looked through. Core's, so a module app gets the same sidebar. What isn't
// set up yet (a property with no rent) is counted in red beside its page.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { api } from "@/src/platform/lib/api";

export default async function Layout({ children }: { children: ReactNode }) {
  // A count that can't be had is left out rather than stopping the page.
  const unset = await api.get<Record<string, number>>("/admin/unset").catch(() => undefined);
  return <ShellLayout unset={unset}>{children}</ShellLayout>;
}
