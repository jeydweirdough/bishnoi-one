// The signed-in frame: the same sidebar as everywhere else, with what waits
// on Finance counted beside its pages, and Finance's version at its foot.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { getFrame } from "@/src/platform/lib/api";
import { Bell } from "@/src/notifications/bell";
import { VersionFooter } from "@/src/version/version-footer";

export default async function Layout({ children }: { children: ReactNode }) {
  // Who, what waits on Finance, what isn't set up and the API's build: one request (GET /finance/frame).
  const frame = await getFrame();
  const waiting = frame.waiting ?? undefined;
  const unset = frame.unset;
  const apiBuild = (frame as { build?: string | null }).build;
  const apiBuildSource = (frame as { buildSource?: string | null }).buildSource;
  // Finance's own field on the frame (the shared kit's Frame type stays as it is).
  const unread = (frame as { unreadNotifications?: number }).unreadNotifications ?? 0;
  return (
    <ShellLayout waiting={waiting} unset={unset} footer={<VersionFooter apiBuild={apiBuild} apiBuildSource={apiBuildSource} />} bell={<Bell unread={unread} />}>
      {children}
    </ShellLayout>
  );
}
