// The route. The screen is in src/, so it can be read on its own.
import { ActivityPage } from "@/src/one/company/screens";

export const metadata = { title: "Activity log" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function Activity({ searchParams }: { searchParams: Search }) {
  const s = await searchParams;
  return <ActivityPage q={one(s.q)} category={one(s.category)} before={one(s.before)} />;
}
