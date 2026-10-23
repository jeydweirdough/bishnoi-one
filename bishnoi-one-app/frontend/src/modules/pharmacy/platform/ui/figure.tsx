import Link from "next/link";
import { Flag } from "@/src/modules/pharmacy/platform/ui/marks";
import { Amount } from "@/src/modules/pharmacy/platform/ui/amount";

/** One number on an overview, under a word for what it counts. A link when
 *  there is a list behind it; a flag when a number above zero wants attention. */
export function Figure({ label, value, href, flag }: { label: string; value: number; href?: string; flag?: boolean }) {
  const figure = <span className="block text-figure text-ink"><Amount text={value.toLocaleString("en")} /></span>;
  return (
    <div className="min-w-0 px-5 py-4">
      {href ? (
        <Link href={href} className="block hover:[&>span:first-child]:text-hema">
          {figure}
        </Link>
      ) : (
        figure
      )}
      <span className="mt-0.5 block text-meta text-ink-3">
        {flag && value > 0 ? <Flag letter="!">{label}</Flag> : label}
      </span>
    </div>
  );
}
