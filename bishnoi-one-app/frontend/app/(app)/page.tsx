import type { Metadata } from "next";
import Link from "next/link";
import { getAccount } from "@/src/platform/lib/account";
import { Banner } from "@/src/platform/ui/alert";
import { Icon } from "@/src/platform/ui/icons";
import { buildMenu } from "@/src/one/menu/one-menu";
import { OneFrame } from "@/src/one/menu/one-frame";

export const metadata: Metadata = { title: "Home" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/**
 * One Home for everyone (M4, the one menu by work, 2026-11-18): the work this person does, grouped as the
 * menu groups it, each group's pages one click away; the overviews (Sales, Stock, Finance, Pharmacy,
 * Employees) lead each group. In place of going straight into a first app (2026-10-24). A page that couldn't
 * be opened sends people here with a notice.
 */
export default async function Home({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const me = await getAccount();
  const menu = buildMenu(me);
  const notice = typeof q.notice === "string" ? q.notice.slice(0, 300) : null;
  const first = me.fullName.split(" ")[0] || me.fullName;
  const groups = [...menu.processes, ...menu.foot];

  return (
    <OneFrame>
      <h1 className="text-3xl tracking-tight">Hello, {first}</h1>
      {me.company && (
        <p className="mt-1 text-sm text-muted-foreground">
          Working in <span className="font-medium text-foreground">{me.company.name}</span>.
        </p>
      )}

      {notice && (
        <Banner tone="warn" className="mt-6">
          {notice}
        </Banner>
      )}

      {groups.length === 0 ? (
        <div className="mt-10 rounded-xl bg-card px-6 py-12 text-center ring-1 ring-foreground/10">
          <p className="text-base font-medium">Nothing to open yet</p>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground">Your account hasn&apos;t been given any work yet. Ask your company&apos;s administrator for the access you need.</p>
        </div>
      ) : (
        <ul className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {groups.map((g) => (
            <li key={g.label} className="flex flex-col gap-3 rounded-xl bg-card py-4 text-card-foreground ring-1 ring-foreground/10">
              <p className="flex items-center gap-2.5 border-b px-4 pb-3 font-medium">
                <span className="grid size-8 place-items-center rounded-lg bg-muted text-foreground">
                  <Icon name={g.icon} className="size-4" />
                </span>
                {g.label}
              </p>
              <ul className="space-y-0.5 px-2">
                {g.steps.map((st) => (
                  <li key={st.href}>
                    <Link href={st.href} className="flex min-h-8 items-center gap-2.5 rounded-md px-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
                      <Icon name={st.icon} className="size-4 shrink-0" />
                      <span className="truncate">{st.label}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </OneFrame>
  );
}
