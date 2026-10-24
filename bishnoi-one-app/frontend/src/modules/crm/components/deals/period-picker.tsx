"use client";

import { DatePicker, Segmented } from "antd";
import { Combobox } from "@/src/platform/ui/pickers";
import dayjs, { type Dayjs } from "dayjs";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";

const CUSTOM = "custom";
const RANGE = /^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$/;

/**
 * The period results are for: a month or quarter from the list, or a range
 * of your own, by day (1 Jul to 15 Oct) or by month (July to October).
 * Kept in the address (?period=, or the name given), so it can be shared and comes back.
 */
export function PeriodPicker({
  value,
  presets,
  name = "period",
  bare = false,
}: {
  value: string;
  presets: { value: string; label: string }[];
  name?: string;
  /** In a toolbar: no label over it, no space under it. */
  bare?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [, start] = useTransition();
  const range = value.match(RANGE);
  const [custom, setCustom] = useState(Boolean(range) || !presets.some((p) => p.value === value));
  const [by, setBy] = useState<"days" | "months">(() => {
    // A range from a month's first day to another's last reads as months.
    if (!range) return "days";
    const [first, last] = [dayjs(range[1]), dayjs(range[2])];
    return first.date() === 1 && last.isSame(last.endOf("month"), "day") ? "months" : "days";
  });
  const picked: [Dayjs, Dayjs] | null = range ? [dayjs(range[1]), dayjs(range[2])] : null;

  function go(period: string) {
    const next = new URLSearchParams(params.toString());
    next.set(name, period);
    start(() => router.replace(`${pathname}?${next}`, { scroll: false }));
  }

  function pickRange(dates: [Dayjs | null, Dayjs | null] | null) {
    if (!dates?.[0] || !dates[1]) return;
    const [first, last] = by === "months" ? [dates[0].startOf("month"), dates[1].endOf("month")] : [dates[0], dates[1]];
    go(`${first.format("YYYY-MM-DD")}..${last.format("YYYY-MM-DD")}`);
  }

  return (
    <div className={bare ? "flex flex-wrap items-center gap-3" : "mb-4 flex flex-wrap items-end gap-3"}>
      <label className="block">
        <span className={bare ? "sr-only" : "mb-1.5 block text-sm text-ink"}>Period</span>
        <Combobox
          className="w-48"
          value={custom ? CUSTOM : value}
          onChange={(v) => {
            if (v === CUSTOM) return setCustom(true);
            setCustom(false);
            go(v);
          }}
          options={[...presets, { value: CUSTOM, label: "Choose dates…" }]}
        />
      </label>
      {custom && (
        <>
          <Segmented<"days" | "months">
            value={by}
            onChange={setBy}
            options={[
              { value: "days", label: "By day" },
              { value: "months", label: "By month" },
            ]}
          />
          <DatePicker.RangePicker
            key={by}
            picker={by === "months" ? "month" : "date"}
            format={by === "months" ? "MMM YYYY" : "D MMM YYYY"}
            value={picked}
            onChange={(dates) => pickRange(dates as [Dayjs | null, Dayjs | null] | null)}
            allowClear={false}
            placeholder={by === "months" ? ["From month", "To month"] : ["From", "To"]}
            presets={[
              { label: "Year to date", value: [dayjs().startOf("year"), dayjs()] },
              { label: "Last 30 days", value: [dayjs().subtract(29, "day"), dayjs()] },
              { label: "Last 12 months", value: [dayjs().subtract(11, "month").startOf("month"), dayjs().endOf("month")] },
            ]}
          />
        </>
      )}
    </div>
  );
}
