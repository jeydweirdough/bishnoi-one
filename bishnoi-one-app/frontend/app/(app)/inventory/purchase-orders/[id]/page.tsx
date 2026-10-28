// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { PurchaseOrderPage } from "@/src/modules/inventory/screens/purchasing";
import { withTrail } from "@/src/platform/ui/document-trail";

export const metadata = { title: "Purchase order" };
export default withTrail(PurchaseOrderPage, "inventory", "purchase_order");
