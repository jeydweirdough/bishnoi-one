"use client";

import { usePathname, useRouter } from "next/navigation";
import { useTransition } from "react";
import { Select } from "@/src/platform/ui/pickers";
import { PERIODS, type PeriodKey } from "./periods";

/** The period, kept in the address (?period=), so it can be shared and comes back. */
export function PeriodSelect({ value }: { value: PeriodKey }) {
  const router = useRouter();
  const pathname = usePathname();
  const [, start] = useTransition();
  return (
    <Select
      aria-label="Period"
      className="w-44"
      value={value}
      onChange={(e) => start(() => router.replace(`${pathname}?period=${e.target.value}`, { scroll: false }))}
    >
      {PERIODS.map((p) => (
        <option key={p.value} value={p.value}>
          {p.label}
        </option>
      ))}
    </Select>
  );
}
