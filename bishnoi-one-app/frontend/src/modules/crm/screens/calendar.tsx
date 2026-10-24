import ActivitiesPage from "@/src/modules/crm/screens/activities";

export const metadata = { title: "Calendar" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/** Calls and visits by day: the activities' calendar, with New call. */
export default function CalendarPage({ searchParams }: { searchParams: Search }) {
  return <ActivitiesPage searchParams={searchParams} calendar />;
}
