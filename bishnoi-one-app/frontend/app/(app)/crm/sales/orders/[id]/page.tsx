// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { SalesOrderPage } from "@/src/modules/sales/screens";
import { withTrail } from "@/src/platform/ui/document-trail";

export const metadata = { title: "Sales order" };
export default withTrail(SalesOrderPage, "inventory", "sales_order");
