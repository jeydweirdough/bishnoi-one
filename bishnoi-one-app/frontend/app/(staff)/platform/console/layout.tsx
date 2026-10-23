// The signed-in frame: the same sidebar as everywhere else, and above every
// page the incidents serious enough to say so. What isn't set up yet (a person
// with no password) is counted in red beside its page.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/modules/console/platform/app/shell-layout";
import { IncidentBanner } from "@/src/modules/console/components/incident-banner";
import { getFrame } from "@/src/modules/console/platform/lib/api";

export default async function Layout({ children }: { children: ReactNode }) {
  // Who, the banner and what isn't set up: one request for all three (GET /platform/frame).
  const { unset } = await getFrame();
  return (
    <ShellLayout unset={unset}>
      <IncidentBanner />
      {children}
    </ShellLayout>
  );
}
