// The route. The screen is in src/, so it can be read on its own.
import { HrRecordsPage } from "@/src/one/access/screens";

export const metadata = { title: "HR records" };

export default async function HrRecords({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return <HrRecordsPage searchParams={searchParams} />;
}
