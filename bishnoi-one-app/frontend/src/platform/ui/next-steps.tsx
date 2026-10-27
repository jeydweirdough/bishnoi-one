import { ArrowRight, type LucideIcon } from "lucide-react";
import Link from "next/link";

// What a record still needs, as the way to it (decided 2026-10-25): on a record's page, under
// its title, the next things to do with it (add products, make a quote, move a date that's
// gone by), each a button that opens the very place to fill it. The first is the one to do
// now; three at most (Hick's law); none at all when the record is complete, so the strip only
// appears when there is something to do.

export type NextStep = { label: string; href: string; icon: LucideIcon; urgent?: boolean };

export function NextSteps({ steps }: { steps: NextStep[] }) {
  const shown = steps.slice(0, 3);
  if (!shown.length) return null;
  return (
    <nav aria-label="To do" className="mb-5 flex flex-wrap items-center gap-2 rounded-xl bg-mint px-3 py-2.5">
      <span className="px-1 text-meta font-semibold text-sage-deep">To do</span>
      {shown.map((s, i) => (
        <Link
          key={s.href + s.label}
          href={s.href}
          className={`group inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors ${
            s.urgent ? "bg-danger text-white hover:bg-danger/90" : i === 0 ? "bg-ink text-white hover:bg-ink/85" : "bg-white text-ink hover:bg-mint-2"
          }`}
        >
          <s.icon className="size-4" aria-hidden />
          {s.label}
          <ArrowRight className="size-3.5 opacity-60 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      ))}
    </nav>
  );
}
