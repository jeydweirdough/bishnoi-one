// The route. The screen is in src/, so it can be read on its own.
import { AccessPeople } from "@/src/one/access/screens";

export const metadata = { title: "People" };

export default async function People({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return <AccessPeople searchParams={searchParams} />;
}
