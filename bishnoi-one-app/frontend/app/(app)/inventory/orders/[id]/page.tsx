// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { OrderPage } from "@/src/modules/inventory/screens/orders";
import { withTrail } from "@/src/platform/ui/document-trail";

export const metadata = { title: "Order" };
export default withTrail(OrderPage, "inventory", "order");
