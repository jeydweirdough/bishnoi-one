// The signed-in frame: the same sidebar as everywhere else, with what waits
// on Finance counted beside its pages, and Finance's version at its foot.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { getFrame } from "@/src/platform/lib/api";
import { VersionFooter } from "@/src/version/version-footer";

export default async function Layout({ children }: { children: ReactNode }) {
  // Who, what waits on Finance, what isn't set up and the API's build: one request (GET /finance/frame).
  const frame = await getFrame();
  const waiting = frame.waiting ?? undefined;
  const unset = frame.unset;
  const apiBuild = (frame as { build?: string | null }).build;
  return (
    <ShellLayout waiting={waiting} unset={unset} footer={<VersionFooter apiBuild={apiBuild} />}>
      {children}
    </ShellLayout>
  );
}
