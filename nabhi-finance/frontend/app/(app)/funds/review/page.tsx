// The route: one step of Fund requests (src/screens/funds.tsx).
import FundsPage from "../../../../src/screens/funds";

export const metadata = { title: "For review" };
export default function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return <FundsPage task="to_check" searchParams={searchParams} />;
}
