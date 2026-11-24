import { cookies } from "next/headers";
import { Suspense, type CSSProperties, type ReactNode } from "react";
import { Separator } from "@/src/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/src/components/ui/sidebar";
import { CrumbsSlot } from "./crumbs";
import { NavProgress } from "./nav-progress";
import { SearchMenu } from "./search-menu";
import { ThemeSwitch } from "./theme-switch";

/**
 * The frame round every signed-in page, as Studio Admin's dashboard layout (shadcn/ui, 2026-11-19): the sidebar
 * (src/platform/shell/sidebar.tsx, given as `nav`), then a 48 px bar along the top with the sidebar button, where
 * you are and search on the left, the page's own actions and your account on the right, then the page.
 * The sidebar's open or collapsed state is kept in shadcn's own cookie, so the next page starts the same.
 */
export async function AppShell({ nav, actions, children }: { nav: ReactNode; actions?: ReactNode; children: ReactNode }) {
  const open = (await cookies()).get("sidebar_state")?.value !== "false";
  return (
    <>
      <Suspense fallback={null}>
        <NavProgress />
      </Suspense>
      <SidebarProvider defaultOpen={open} style={{ "--sidebar-width": "calc(var(--spacing) * 68)" } as CSSProperties}>
        {nav}
        <SidebarInset className="min-w-0 overflow-x-clip">
          <header className="sticky top-0 z-40 flex h-12 shrink-0 items-center gap-2 overflow-hidden rounded-t-[inherit] border-b bg-background/50 backdrop-blur-md print:hidden">
            <div className="flex w-full min-w-0 items-center justify-between gap-2 px-4 lg:px-6">
              <div className="flex min-w-0 flex-1 items-center gap-1 lg:gap-2">
                <SidebarTrigger className="-ml-1" />
                <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4 data-[orientation=vertical]:self-center" />
                <SearchMenu />
                <Separator orientation="vertical" className="mx-2 hidden data-[orientation=vertical]:h-4 data-[orientation=vertical]:self-center md:block" />
                <div className="hidden min-w-0 flex-1 md:flex">
                  <CrumbsSlot />
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <ThemeSwitch />
                {actions}
              </div>
            </div>
          </header>
          <div className="min-h-0 min-w-0 flex-1 overflow-x-hidden p-4 md:p-6">
            <div className="mx-auto w-full max-w-screen-2xl">{children}</div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </>
  );
}
