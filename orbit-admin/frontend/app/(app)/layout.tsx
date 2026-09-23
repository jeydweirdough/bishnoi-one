// The signed-in frame: the sidebar, and the banner when somebody is being
// looked through. Core's, so a module app gets the same sidebar.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";

export default function Layout({ children }: { children: ReactNode }) {
  return <ShellLayout>{children}</ShellLayout>;
}
