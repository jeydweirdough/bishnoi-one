// The signed-in frame: the same sidebar every Nabhi app wears.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";

export default function Layout({ children }: { children: ReactNode }) {
  return <ShellLayout>{children}</ShellLayout>;
}
