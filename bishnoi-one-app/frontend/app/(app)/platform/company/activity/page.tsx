// The route. The screen is in src/, so it can be read on its own.
import { ActivityPage } from "@/src/one/company/screens";

export const metadata = { title: "Activity log" };

type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function Activity({ searchParams }: { searchParams: Search }) {
  return <ActivityPage search={await searchParams} />;
}
