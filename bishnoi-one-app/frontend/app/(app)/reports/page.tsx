import type { Metadata } from "next";
import Link from "next/link";
import { getAccount } from "@/src/platform/lib/account";
import { Icon } from "@/src/platform/ui/icons";
import { reportCentres } from "@/src/one/menu/one-menu";
import { OneFrame } from "@/src/one/menu/one-frame";

export const metadata: Metadata = { title: "Reports" };

/**
 * The one Reports row (M4, 2026-11-18): every report this person may see, by the work, whichever module keeps
 * the data. Each opens that part's Reports Center, which lists its reports for the viewer's role.
 */
export default async function Reports() {
  const centres = reportCentres(await getAccount());
  return (
    <OneFrame>
      <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.02em] text-ink">Reports</h1>
      {centres.length === 0 ? (
        <p className="mt-6 text-sm text-ink-2">No reports for your role yet. Ask your company&apos;s administrator for the access you need.</p>
      ) : (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {centres.map((c) => (
            <li key={c.href}>
              <Link href={c.href} className="flex h-full items-start gap-3 rounded-2xl border border-rule bg-card p-5 transition-colors hover:border-ink">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-mint-2 text-sage-deep">
                  <Icon name={c.icon} className="size-5" />
                </span>
                <span className="min-w-0">
                  <span className="block text-base font-semibold text-ink">{c.label}</span>
                  <span className="mt-0.5 block text-sm text-ink-2">{c.says}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </OneFrame>
  );
}
