import type { ReactNode } from "react";
import { LinkButton } from "@/src/modules/admin/platform/ui/button";
import { Sheet } from "@/src/modules/admin/platform/ui/sheet";
import { getMe } from "@/src/modules/admin/platform/lib/api";

// Who reaches which settings screen.
//
// Settings has two keys. `manage` runs the company — every screen, business
// rules included. `recover` is the narrower one a Developer Admin holds: the
// company record, its accounts, the applications it reaches and the audit log,
// for when something is broken. Owning the company is neither; it is set on the
// membership, so no admin can grant it to themselves.
//
// Each page says which it needs, the same way each route in app/deps.py does,
// because the API is what actually decides. A page that only checked the
// sidebar would 403 halfway through loading; this refuses first, in words.

async function refuse(who: string): Promise<ReactNode | null> {
  return (
    <Sheet className="px-6 py-10 text-center">
      <h1 className="text-heading">This one is {who}</h1>
      <p className="mx-auto mt-1 max-w-md text-ink-2">
        You reach the settings in your sidebar. If you need something that isn&apos;t there, ask whoever runs Bishnoi One for your
        company.
      </p>
      <LinkButton href="/admin" className="mt-5">
        Go home
      </LinkButton>
    </Sheet>
  );
}

/** A business screen: the company's own rules, for whoever runs it. */
export async function managersOnly(): Promise<ReactNode | null> {
  const me = await getMe();
  return me.canManageSettings ? null : refuse("for admins");
}

/** The platform itself, above every company. Only a Developer Admin. */
export async function developersOnly(): Promise<ReactNode | null> {
  const me = await getMe();
  return me.isDeveloperAdmin ? null : refuse("for developer admins");
}

/** What the company *is*. Its owner, or whoever was trusted with recovery —
 *  never a plain Admin, who runs the company without deciding it. */
export async function ownersOnly(): Promise<ReactNode | null> {
  const me = await getMe();
  return me.isOwner || me.canRecover ? null : refuse("the company owner's");
}
