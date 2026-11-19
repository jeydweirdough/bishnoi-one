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
      <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.02em] text-ink">Welcome, {first}</h1>
      {me.company && (
        <p className="mt-1.5 text-sm text-ink-2">
          Working in <span className="font-medium text-ink">{me.company.name}</span>.
        </p>
      )}

      {notice && (
        <Banner tone="warn" className="mt-6">
          {notice}
        </Banner>
      )}

      {groups.length === 0 ? (
        <div className="mt-10 rounded-2xl border border-rule bg-white px-6 py-12 text-center">
          <p className="text-base font-semibold text-ink">Nothing to open yet</p>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-ink-2">Your account hasn&apos;t been given any work yet. Ask your company&apos;s administrator for the access you need.</p>
        </div>
      ) : (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {groups.map((g) => (
            <li key={g.label} className="rounded-2xl border border-rule bg-white p-5">
              <p className="flex items-center gap-2.5 text-base font-semibold text-ink">
                <span className="grid size-9 place-items-center rounded-xl bg-mint-2 text-sage-deep">
                  <Icon name={g.icon} className="size-4" />
                </span>
                {g.label}
              </p>
              <ul className="mt-3 space-y-0.5">
                {g.steps.map((st) => (
                  <li key={st.href}>
                    <Link href={st.href} className="flex min-h-9 items-center gap-2.5 rounded-lg px-2 text-sm text-ink-2 hover:bg-bench hover:text-ink">
                      <Icon name={st.icon} className="size-4 shrink-0 text-ink-3" />
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
