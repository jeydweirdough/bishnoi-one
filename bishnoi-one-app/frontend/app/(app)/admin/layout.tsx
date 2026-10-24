// The signed-in frame: the sidebar, and the banner when somebody is being
// looked through. Core's, so a module app gets the same sidebar. What isn't
// set up yet (a property with no rent) is counted in red beside its page.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/modules/admin/platform/app/shell-layout";
import { getFrame } from "@/src/modules/admin/platform/lib/api";

export default async function Layout({ children }: { children: ReactNode }) {
  // Who you are and the red counts, in one request; a count that can't be had
  // is left out rather than stopping the page.
  const { unset } = await getFrame();
  return <ShellLayout unset={unset ?? undefined}>{children}</ShellLayout>;
}
