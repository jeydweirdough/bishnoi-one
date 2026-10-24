// The signed-in frame: the same sidebar every Bishnoi One app wears, with how many
// things wait on this person beside each place they work in.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/modules/inventory/platform/app/shell-layout";
import { getFrame } from "@/src/modules/inventory/platform/lib/api";
import { AlertsBell } from "@/src/modules/inventory/components/alerts-bell";

export default async function Layout({ children }: { children: ReactNode }) {
  // One request with who you are: the API only lists what this person's role
  // may act on, and what isn't set up yet (a product with no price). Counts are
  // a help, not the page: without them the sidebar still works.
  const { alerts, unset } = await getFrame();
  const waiting = Object.fromEntries((alerts ?? []).map((a) => [a.key, a.count]));
  return (
    <ShellLayout waiting={waiting} unset={unset ?? {}} bell={<AlertsBell alerts={alerts ?? []} />}>
      {children}
    </ShellLayout>
  );
}
