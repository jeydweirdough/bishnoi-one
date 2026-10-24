import type { ReactNode } from "react";
import { getAccount } from "@/src/platform/lib/account";
import { AccountMenu } from "@/src/one/account-menu";
import { Brand } from "@/src/one/brand";
import { myModules } from "@/src/one/mine";
import { ModuleSwitcher } from "@/src/one/module-switcher";

// Every signed-in page of the one app: a thin bar on top (the brand, which
// module you're in and the others you have, your company and account), then
// the page. A module brings its own menu inside its pages (its layout).
export default async function AppLayout({ children }: { children: ReactNode }) {
  const me = await getAccount();
  return (
    <div className="min-h-dvh bg-bench">
      <header className="sticky top-0 z-40 border-b border-rule bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[90rem] items-center gap-4 px-4 sm:px-6">
          <Brand />
          <span className="h-6 w-px bg-rule" aria-hidden />
          <ModuleSwitcher mine={myModules(me)} />
          <span className="flex-1" />
          <AccountMenu id={me.id} name={me.fullName} email={me.email} companies={me.companies} />
        </div>
      </header>
      {children}
    </div>
  );
}
