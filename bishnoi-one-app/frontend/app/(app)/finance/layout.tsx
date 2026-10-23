// The signed-in frame: the same sidebar as everywhere else, with what waits
// on Finance counted beside its pages.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/modules/finance/platform/app/shell-layout";
import { getFrame } from "@/src/modules/finance/platform/lib/api";

export default async function Layout({ children }: { children: ReactNode }) {
  // Who, what waits on Finance and what isn't set up: one request (GET /finance/frame).
  const frame = await getFrame();
  const waiting = frame.waiting ?? undefined;
  const unset = frame.unset;
  return (
    <ShellLayout waiting={waiting} unset={unset}>
      {children}
    </ShellLayout>
  );
}
