// The signed-in frame: the same sidebar every Bishnoi One app wears. A field agent
// also needs their location on while the CRM is open in work hours (a guide
// stands in front of it until it is), and their trail is taken, with a
// marker in the corner saying so.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { getFrame } from "@/src/platform/lib/api";
import { FieldTracker } from "@/src/components/field/tracker";
import { CanProvider } from "@/src/components/quick-add/can";
import { isFieldAgent } from "@/src/components/field/words";
import { TermsProvider } from "@/src/components/terms/provider";
import { termsOf } from "@/src/components/terms/terms";

export default async function Layout({ children }: { children: ReactNode }) {
  // Who you are and what isn't set up yet (a product with no price, in red):
  // one request, shared with the page below (lib/api.ts getFrame).
  const { me, unset: counts } = await getFrame();
  const unset = counts ?? undefined;
  return (
    <ShellLayout unset={unset}>
      <TermsProvider terms={termsOf(me)}>
        <CanProvider permissions={me.permissions ?? []}>{children}</CanProvider>
      </TermsProvider>
      {isFieldAgent(me) && me.org && <FieldTracker userId={me.user.id} timeZone={me.org.timezone} />}
    </ShellLayout>
  );
}
