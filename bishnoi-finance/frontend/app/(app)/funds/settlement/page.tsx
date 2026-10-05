// The route: one step of Marketing requests (src/screens/funds.tsx).
import FundsPage from "../../../../src/screens/funds";

export const metadata = { title: "For settlement" };
export default function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return <FundsPage task="to_settle" searchParams={searchParams} />;
}
