import "server-only";
import type { ReactNode } from "react";
import { LinkButton } from "@/src/modules/console/platform/ui/button";
import { Sheet } from "@/src/modules/console/platform/ui/sheet";
import { getMe } from "@/src/modules/console/platform/lib/api";
import type { StaffMe } from "@/src/modules/console/lib/types";

// Who may do what here. Everyone signed in is staff and sees everything;
// changing the platform takes a Platform Admin. The API decides (app/deps.py);
// the screens ask so they can hide what would only be refused.

/** Which kind of staff is signed in. */
export async function getStaff(): Promise<StaffMe> {
  const me = (await getMe()) as unknown as Partial<StaffMe>;
  return {
    platformRole: me.platformRole ?? "member",
    platformRoleName: me.platformRoleName ?? "Support",
    canAdminister: me.canAdminister ?? false,
  };
}

/** A page only a Platform Admin can use. Null lets them through. */
export async function adminsOnly(): Promise<ReactNode | null> {
  const staff = await getStaff();
  if (staff.canAdminister) return null;
  return (
    <Sheet className="px-6 py-10 text-center">
      <h1 className="text-heading">Platform Admin access required</h1>
      <p className="mx-auto mt-1 max-w-md text-ink-2">
        Support sees everything on the platform and works its tickets and incidents. Changing it takes a Platform Admin.
      </p>
      <LinkButton href="/platform" className="mt-5">
        Go to the dashboard
      </LinkButton>
    </Sheet>
  );
}
