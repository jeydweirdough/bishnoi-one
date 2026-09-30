// The signed-in frame: the same sidebar as everywhere else, with what waits
// on Finance counted beside its pages.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { api } from "@/src/platform/lib/api";

export default async function Layout({ children }: { children: ReactNode }) {
  // A count that can't be had is left out rather than stopping the page.
  const [waiting, unset] = await Promise.all([
    api.get<Record<string, number>>("/finance/funds/counts").catch(() => undefined),
    // What an admin hasn't set up yet (a default account), in red.
    api.get<Record<string, number>>("/finance/unset").catch(() => undefined),
  ]);
  return (
    <ShellLayout waiting={waiting} unset={unset}>
      {children}
    </ShellLayout>
  );
}
