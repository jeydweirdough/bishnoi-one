// The route: one step of Marketing requests (src/screens/funds.tsx).
import FundsPage from "@/src/modules/finance/screens/funds";

export const metadata = { title: "Outstanding cash advances" };
export default function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return <FundsPage task="to_liquidate" searchParams={searchParams} />;
}
