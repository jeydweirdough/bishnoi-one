import Link from "next/link";
import type { ReactNode } from "react";
import { Flag } from "@/src/platform/ui/marks";
import { Sheet } from "@/src/platform/ui/sheet";

/** A row of headline numbers, hairlines between them. */
const COLUMNS = { 3: "sm:grid-cols-3", 4: "sm:grid-cols-2 lg:grid-cols-4", 5: "sm:grid-cols-3 xl:grid-cols-5" } as const;

export function Stats({ children, columns = 5 }: { children: ReactNode; columns?: keyof typeof COLUMNS }) {
  return <Sheet className={`mb-5 grid grid-cols-2 gap-px overflow-hidden bg-rule ${COLUMNS[columns]} [&>*]:bg-sheet`}>{children}</Sheet>;
}

/** One number, what it counts, and where to see the list behind it. `flag` marks it when it's above zero. */
export function Stat({ label, value, note, href, flag }: { label: string; value: number | string; note?: string; href?: string; flag?: boolean }) {
  const figure = <span className={`block text-figure ${flag && typeof value === "number" && value > 0 ? "text-danger" : "text-ink"}`}>{value}</span>;
  return (
    <div className="min-w-0 px-5 py-4">
      {href ? (
        <Link href={href} className="block hover:[&>span:first-child]:text-ink">
          {figure}
        </Link>
      ) : (
        figure
      )}
      <span className="mt-0.5 block text-meta text-ink-3">{flag && typeof value === "number" && value > 0 ? <Flag letter="!">{label}</Flag> : label}</span>
      {note && <span className="block text-meta text-ink-3">{note}</span>}
    </div>
  );
}
