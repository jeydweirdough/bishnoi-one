import type { ReactNode } from "react";
import { Separator } from "@/src/components/ui/separator";
import { APP_NAME } from "@/src/platform/lib/labels";
import { Brand } from "@/src/one/brand";

/**
 * Every sign-in page's frame (sign in, forgot password, a link's new password, the first sign-in, setup), as Studio
 * Admin's two-column login (2026-11-19): the form on the left, the brand panel on the right (hidden on a phone).
 * With `title`, a 350 px column with the title and intro; without, the page lays itself out (the two-step set-up).
 */
export function SignInShell({ title, intro, children, home = "/login" }: { title?: string; intro?: ReactNode; children: ReactNode; home?: string }) {
  return (
    <main>
      <div className="grid min-h-dvh justify-center p-2 lg:grid-cols-2">
        <div className="relative order-2 hidden min-h-full rounded-3xl bg-primary lg:flex">
          <div className="absolute top-10 space-y-1 px-10 text-primary-foreground">
            <img src="/brand/bishnoi-one-mark.png" alt="" width={40} height={40} className="size-10 rounded-lg bg-white p-1" />
            <h2 className="text-2xl font-medium">{APP_NAME}</h2>
            <p className="text-sm">Customers, stock and the books, in one place.</p>
          </div>
          <div className="absolute bottom-10 flex w-full justify-between px-10">
            <div className="flex-1 space-y-1 text-primary-foreground">
              <h3 className="font-medium">One account</h3>
              <p className="text-sm">One sign-in opens every part your company gives you: CRM, Inventory, Finance and more.</p>
            </div>
            <Separator orientation="vertical" className="mx-3 h-auto! bg-primary-foreground/20" />
            <div className="flex-1 space-y-1 text-primary-foreground">
              <h3 className="font-medium">Need access?</h3>
              <p className="text-sm">Use the link in your invitation email, or ask your company&apos;s administrator.</p>
            </div>
          </div>
        </div>
        <div className="relative order-1 flex min-h-full py-20">
          {title ? (
            <div className="mx-auto flex w-full flex-col justify-center space-y-8 px-4 sm:w-[350px] sm:px-0">
              <div className="space-y-2 text-center">
                <h1 className="text-3xl font-medium">{title}</h1>
                {intro && <div className="text-sm text-muted-foreground">{intro}</div>}
              </div>
              {children}
            </div>
          ) : (
            <div className="mx-auto flex w-full max-w-2xl flex-col justify-center px-4">{children}</div>
          )}
          <div className="absolute top-5 flex w-full justify-start px-6 sm:px-10">
            <Brand href={home} />
          </div>
          <div className="absolute bottom-5 flex w-full justify-between px-6 text-sm text-muted-foreground sm:px-10">
            <span>
              © {new Date().getFullYear()} {APP_NAME}
            </span>
          </div>
        </div>
      </div>
    </main>
  );
}
