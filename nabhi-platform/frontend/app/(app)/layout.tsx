// The signed-in frame: the same sidebar as everywhere else.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";

export default function Layout({ children }: { children: ReactNode }) {
  return <ShellLayout>{children}</ShellLayout>;
}
