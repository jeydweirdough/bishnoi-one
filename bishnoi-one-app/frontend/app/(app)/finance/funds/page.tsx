// The route: Marketing requests, one page with a tab for each stage (src/screens/funds.tsx).
import FundsPage from "@/src/modules/finance/screens/funds";

export const metadata = { title: "Marketing requests" };
export default function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return <FundsPage searchParams={searchParams} />;
}
