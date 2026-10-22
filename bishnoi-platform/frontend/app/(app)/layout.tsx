// The signed-in frame: the same sidebar as everywhere else, and above every
// page the incidents serious enough to say so. What isn't set up yet (a person
// with no password) is counted in red beside its page.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { IncidentBanner } from "@/src/components/incident-banner";
import { getFrame } from "@/src/platform/lib/api";
import { followAddress } from "@/src/platform/lib/follow-address";

export default async function Layout({ children }: { children: ReactNode }) {
  // Who, the banner and what isn't set up: one request for all three (GET /platform/frame).
  const { unset } = await getFrame();
  // The apps' addresses follow the one the platform is opened at (lib/follow-address.ts).
  await followAddress();
  return (
    <ShellLayout unset={unset}>
      <IncidentBanner />
      {children}
    </ShellLayout>
  );
}
