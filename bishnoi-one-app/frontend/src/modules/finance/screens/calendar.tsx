import { PageHeader } from "@/src/modules/finance/platform/ui/sheet";
import { load } from "@/src/modules/finance/platform/lib/api";
import { gridDays } from "@/src/modules/finance/calendar/grid";
import { CalendarMonth } from "@/src/modules/finance/calendar/month";
import type { CalendarData } from "@/src/modules/finance/calendar/types";

// Finance → Calendar, for whoever has it switched on (Administration → Users). A
// 403 from the API (it isn't on for this person) shows the access-denied page.

export const metadata = { title: "Calendar" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function CalendarPage({ searchParams }: { searchParams: Search }) {
  const sp = await searchParams;
  // A reminder links to /calendar?on=<date>&event=<id>: open that month with it picked.
  const on = /^\d{4}-\d{2}-\d{2}$/.test(one(sp.on)) ? one(sp.on) : "";
  const asked = /^\d{4}-\d{2}$/.test(one(sp.month)) ? one(sp.month) : on.slice(0, 7);
  // Without a month, the API answers for this month; ask it which that is first.
  const month = asked || (await load<CalendarData>("/finance/calendar")).today.slice(0, 7);
  const days = gridDays(month);
  const data = await load<CalendarData>(`/finance/calendar?from=${days[0]}&to=${days[days.length - 1]}`);
  const event = one(sp.event);
  return (
    <>
      <PageHeader title="Calendar">
        Your deadlines, cut-offs and monthly tasks, and those shared with you. Finance reminds you in the bell and on the Overview, on the day or some working days
        before (Monday to Saturday, not counting holidays).
      </PageHeader>
      <CalendarMonth data={data} month={month} picked={on && event ? { event, on } : null} />
    </>
  );
}
