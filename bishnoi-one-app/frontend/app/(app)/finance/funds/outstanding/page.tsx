// The route: one step of Marketing requests (src/screens/funds.tsx).
import FundsPage from "@/src/modules/finance/screens/funds";

export const metadata = { title: "Outstanding cash advances" };
export default function Page() {
  return <FundsPage task="to_liquidate" />;
}
