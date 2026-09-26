// The route: one step of Fund requests (src/screens/funds.tsx).
import FundsPage from "../../../../src/screens/funds";

export const metadata = { title: "Outstanding cash advances" };
export default function Page() {
  return <FundsPage task="to_liquidate" />;
}
