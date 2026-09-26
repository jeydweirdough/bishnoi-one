// The signed-in frame: the same sidebar every Nabhi app wears. A field agent
// also needs their location on while the CRM is open in work hours (a guide
// stands in front of it until it is), and their trail is taken, with a
// marker in the corner saying so.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { api, getMe } from "@/src/platform/lib/api";
import { FieldTracker } from "@/src/components/field/tracker";
import { CanProvider } from "@/src/components/quick-add/can";
import { isFieldAgent } from "@/src/components/field/words";

export default async function Layout({ children }: { children: ReactNode }) {
  const me = await getMe();
  // What waits on them, for the sidebar's counts. A count that can't be had
  // is left out rather than stopping the page.
  const waiting = me.permissions?.includes("funds.view") ? await api.get<Record<string, number>>("/funds/waiting").catch(() => undefined) : undefined;
  return (
    <ShellLayout waiting={waiting}>
      <CanProvider permissions={me.permissions ?? []}>{children}</CanProvider>
      {isFieldAgent(me) && me.org && <FieldTracker userId={me.user.id} timeZone={me.org.timezone} />}
    </ShellLayout>
  );
}
