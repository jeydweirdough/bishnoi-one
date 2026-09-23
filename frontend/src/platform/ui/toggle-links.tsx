import Link from "next/link";

/** A segmented switch made of links, so the choice lives in the URL. */
export function ToggleLinks({ options, current }: { options: { href: string; label: string; value: string }[]; current: string }) {
  return (
    <div className="inline-flex rounded-[3px] border border-rule-strong bg-sheet p-0.5">
      {options.map((o) => (
        <Link
          key={o.value}
          href={o.href}
          scroll={false} // a filter changes what's below it; the page shouldn't jump back to the top
          aria-current={o.value === current ? "true" : undefined}
          className={`rounded-[2px] px-3 py-1 text-meta ${
            o.value === current ? "bg-hema-tint font-semibold text-hema" : "text-ink-2 hover:text-ink"
          }`}
        >
          {o.label}
        </Link>
      ))}
    </div>
  );
}
