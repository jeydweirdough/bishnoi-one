// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { CountPage } from "@/src/modules/inventory/screens/adjustments";
import { withTrail } from "@/src/platform/ui/document-trail";

export const metadata = { title: "Inventory count" };
export default withTrail(CountPage, "inventory", "count");
