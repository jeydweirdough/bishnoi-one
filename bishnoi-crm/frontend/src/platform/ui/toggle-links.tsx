"use client";

import { Segmented } from "antd";
import Link from "next/link";
import { useRouter } from "next/navigation";

/**
 * A switch between views, as Ant Design's segmented control. Each option is a
 * real link, so the choice lives in the URL (and opens in a new tab if asked).
 */
export function ToggleLinks({ options, current }: { options: { href: string; label: string; value: string }[]; current: string }) {
  const router = useRouter();
  return (
    <Segmented
      value={current}
      onChange={(v) => {
        const o = options.find((x) => x.value === v);
        // a filter changes what's below it; the page shouldn't jump back to the top
        if (o) router.push(o.href, { scroll: false });
      }}
      options={options.map((o) => ({
        value: o.value,
        label: (
          <Link href={o.href} scroll={false} aria-current={o.value === current ? "true" : undefined} className="block text-inherit">
            {o.label}
          </Link>
        ),
      }))}
    />
  );
}
