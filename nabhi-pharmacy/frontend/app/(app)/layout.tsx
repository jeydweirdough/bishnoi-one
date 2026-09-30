// The signed-in frame: the same sidebar every Nabhi app wears, with what
// isn't set up yet (a medicine with no price) counted in red.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { api } from "@/src/platform/lib/api";

export default async function Layout({ children }: { children: ReactNode }) {
  // A count that can't be had is left out rather than stopping the page.
  const unset = await api.get<Record<string, number>>("/unset").catch(() => undefined);
  return <ShellLayout unset={unset}>{children}</ShellLayout>;
}
