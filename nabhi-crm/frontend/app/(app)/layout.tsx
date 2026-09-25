// The signed-in frame: the same sidebar every Nabhi app wears. A field agent
// also needs their location on while the CRM is open in work hours (a guide
// stands in front of it until it is), and their trail is taken, with a
// marker in the corner saying so.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { getMe } from "@/src/platform/lib/api";
import { FieldTracker } from "@/src/components/field/tracker";
import { isFieldAgent } from "@/src/components/field/words";

export default async function Layout({ children }: { children: ReactNode }) {
  const me = await getMe();
  return (
    <ShellLayout>
      {children}
      {isFieldAgent(me) && me.org && <FieldTracker userId={me.user.id} timeZone={me.org.timezone} />}
    </ShellLayout>
  );
}
