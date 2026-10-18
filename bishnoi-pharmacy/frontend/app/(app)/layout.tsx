// The signed-in frame: the same sidebar every Bishnoi One app wears, with what
// isn't set up yet (a medicine with no price) counted in red.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { getFrame } from "@/src/platform/lib/api";

export default async function Layout({ children }: { children: ReactNode }) {
  // Who and what isn't set up: one request (GET /frame).
  const { unset } = await getFrame();
  return <ShellLayout unset={unset}>{children}</ShellLayout>;
}
