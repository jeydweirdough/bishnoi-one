// The signed-in frame: the same sidebar as everywhere else, and above every
// page the incidents serious enough to say so. What isn't set up yet (a person
// with no password) is counted in red beside its page.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { IncidentBanner } from "@/src/components/incident-banner";
import { api } from "@/src/platform/lib/api";

export default async function Layout({ children }: { children: ReactNode }) {
  // A count that can't be had is left out rather than stopping the page.
  const unset = await api.get<Record<string, number>>("/platform/unset").catch(() => undefined);
  return (
    <ShellLayout unset={unset}>
      <IncidentBanner />
      {children}
    </ShellLayout>
  );
}
