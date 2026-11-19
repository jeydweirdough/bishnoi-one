import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Separator } from "@/src/components/ui/separator";
import { accountCall, accountToken, type Account } from "@/src/platform/lib/account";
import { APP_NAME } from "@/src/platform/lib/labels";
import { Brand } from "@/src/one/brand";
import { LoginForm } from "@/src/one/login-form";

export const metadata: Metadata = { title: "Sign in to Bishnoi One" };

type Search = Promise<Record<string, string | string[] | undefined>>;


/**
 * The one app's sign-in (decided 2026-10-23): one Bishnoi One account for every
 * module. Someone already signed in goes straight on.
 */
export default async function LoginPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const asked = typeof q.next === "string" ? q.next : "/";
  const next = asked.startsWith("/") && !asked.startsWith("//") ? asked : "/";
  const expired = q.expired === "1";

  // A new Bishnoi One with nobody in it yet: set it up first (app/setup).
  const setup = await accountCall<{ needed: boolean }>("/setup").catch(() => null);
  if (setup?.needed) redirect("/setup");

  const token = await accountToken();
  if (token) {
    const me = await accountCall<Account>("/identity/me", undefined, token).catch(() => null);
    if (me) redirect(next);
  }

  // Studio Admin's two-column login (2026-11-19): the form on the left, the brand panel on the right.
  return (
    <main>
      <div className="grid h-dvh justify-center p-2 lg:grid-cols-2">
        <div className="relative order-2 hidden h-full rounded-3xl bg-primary lg:flex">
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
        <div className="relative order-1 flex h-full">
          <div className="mx-auto flex w-full flex-col justify-center space-y-8 px-4 sm:w-[350px] sm:px-0">
            <div className="space-y-2 text-center">
              <h1 className="text-3xl font-medium">Sign in to your account</h1>
              <p className="text-sm text-muted-foreground">Enter your work email and password.</p>
            </div>
            {expired && <p className="rounded-lg bg-muted px-4 py-2.5 text-center text-sm text-muted-foreground">Your session ended. Sign in again to pick up where you left off.</p>}
            <LoginForm next={next} email={typeof q.email === "string" ? q.email : ""} />
          </div>
          <div className="absolute top-5 flex w-full justify-start px-6 sm:px-10">
            <Brand href="/login" />
          </div>
          <div className="absolute bottom-5 flex w-full justify-between px-6 text-sm text-muted-foreground sm:px-10">
            <span>© {new Date().getFullYear()} {APP_NAME}</span>
          </div>
        </div>
      </div>
    </main>
  );
}
