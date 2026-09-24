// The signed-in frame: the same sidebar as everywhere else, and above every
// page the incidents serious enough to say so.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { IncidentBanner } from "@/src/components/incident-banner";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <ShellLayout>
      <IncidentBanner />
      {children}
    </ShellLayout>
  );
}
