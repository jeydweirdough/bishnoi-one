// The route. The screen is in src/, so it can be read on its own.
import { DataCleanupConsolePage } from "@/src/one/company/data-cleanup";

export const metadata = { title: "Data clean-up" };

type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function DataCleanup({ searchParams }: { searchParams: Search }) {
  return <DataCleanupConsolePage search={await searchParams} />;
}
