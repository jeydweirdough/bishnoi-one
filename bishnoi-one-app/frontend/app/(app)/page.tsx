import { ArrowUpRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { MODULES } from "@/src/platform/lib/modules";
import { Banner } from "@/src/platform/ui/alert";
import { myModules, primaryModule } from "@/src/one/mine";

export const metadata: Metadata = { title: "Bishnoi One" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/**
 * Home is no stop (decided 2026-10-24): someone signed in goes straight into
 * their first module, the first one given to them; the switcher in the bar
 * takes them to the others. This page shows only when there's something to say
 * (a module that couldn't be opened sends them here with a notice), or when
 * they've been given no module at all.
 */
export default async function Home({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const me = await getAccount();
  const mine = myModules(me);
  const list = MODULES.filter((m) => mine.some((x) => x.key === m.key));
  const notice = typeof q.notice === "string" ? q.notice.slice(0, 300) : null;
  const primary = primaryModule(me);
  if (!notice && primary) redirect(primary.path);
  const first = me.fullName.split(" ")[0] || me.fullName;

  return (
    <main className="mx-auto max-w-[90rem] px-4 py-8 sm:px-6 sm:py-10">
      <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.02em] text-ink">Welcome, {first}</h1>
      <p className="mt-1.5 text-sm text-ink-2">
        {me.company ? <>Working in <span className="font-medium text-ink">{me.company.name}</span>. </> : null}
        Pick a module to start.
      </p>

      {notice && (
        <Banner tone="warn" className="mt-6">
          {notice}
        </Banner>
      )}

      {list.length === 0 ? (
        <div className="mt-10 rounded-2xl border border-rule bg-white px-6 py-12 text-center">
          <p className="text-base font-semibold text-ink">No modules yet</p>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-ink-2">Your account hasn&apos;t been given any modules. Ask your company&apos;s administrator to give you the ones you need.</p>
        </div>
      ) : (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {list.map((m) => {
            const old = mine.find((x) => x.key === m.key)?.oldUrl;
            const inner = (
              <>
                <span className="grid size-12 place-items-center rounded-2xl" style={{ background: m.tint, color: m.ink }}>
                  <m.icon className="size-6" aria-hidden />
                </span>
                <span className="mt-4 flex items-center gap-1.5 text-base font-semibold text-ink">
                  {m.label}
                  {m.status === "moving" && old && <ArrowUpRight className="size-4 text-ink-3" aria-hidden />}
                </span>
                <span className="mt-0.5 text-sm text-ink-2">{m.blurb}</span>
                {m.status !== "live" && (
                  <span className="mt-3 inline-flex self-start rounded-full bg-bench px-2.5 py-0.5 text-meta text-ink-3">
                    {m.status === "soon" ? "Coming soon" : "Opens its current app for now"}
                  </span>
                )}
              </>
            );
            const cls = "flex h-full flex-col rounded-2xl border border-rule bg-white p-5 transition-colors";
            return (
              <li key={m.key}>
                {m.status === "soon" ? (
                  <div className={`${cls} opacity-70`} aria-disabled>
                    {inner}
                  </div>
                ) : m.status === "moving" && old ? (
                  <a href={old} className={`${cls} hover:border-ink`}>
                    {inner}
                  </a>
                ) : (
                  <Link href={m.path} className={`${cls} hover:border-ink`}>
                    {inner}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
