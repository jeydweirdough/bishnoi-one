import { LinkButton } from "@/src/modules/admin/platform/ui/button";
import { Sheet } from "@/src/modules/admin/platform/ui/sheet";
import { getMe } from "@/src/modules/admin/platform/lib/api";

// The floor for the whole section: you are here at all because you hold one of
// the two keys to Settings. Which screens each key opens is on the screens
// themselves (components/settings/gate.tsx), because they differ.
export default async function SettingsLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  if (!me.canManageSettings && !me.canRecover) {
    return (
      <Sheet className="px-6 py-10 text-center">
        <h1 className="text-heading">Settings are for admins</h1>
        <p className="mx-auto mt-1 max-w-md text-ink-2">If you need to change who can see what, ask one of your admins.</p>
        <LinkButton href="/admin" className="mt-5">
          Go home
        </LinkButton>
      </Sheet>
    );
  }
  return children;
}
