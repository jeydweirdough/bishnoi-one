// The old address of one stage of Marketing requests: now a tab on /finance/funds (src/screens/funds.tsx).
// Kept so notifications, calendar items and bookmarks still land; the rest of the query is kept.
import { stageRedirect } from "@/src/modules/finance/screens/funds";

export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return stageRedirect("history", searchParams);
}
