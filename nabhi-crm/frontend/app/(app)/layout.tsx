// The signed-in frame: the same sidebar every Nabhi app wears. A field agent
// also gets their trail taken while the CRM is open (in work hours), with a
// marker in the corner saying so.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { can } from "@/src/platform/lib/access";
import { getMe } from "@/src/platform/lib/api";
import { FieldTracker } from "@/src/components/field/tracker";

export default async function Layout({ children }: { children: ReactNode }) {
  const me = await getMe();
  const fieldAgent = can(me, "visits.create") && !can(me, "quotes.view") && !can(me, "goals.view");
  return (
    <ShellLayout>
      {children}
      {fieldAgent && me.org && <FieldTracker userId={me.user.id} timeZone={me.org.timezone} />}
    </ShellLayout>
  );
}
