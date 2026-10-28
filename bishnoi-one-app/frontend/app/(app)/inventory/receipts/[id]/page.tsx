// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { ReceiptPage } from "@/src/modules/inventory/screens/purchasing";
import { withTrail } from "@/src/platform/ui/document-trail";

export const metadata = { title: "Receipt" };
export default withTrail(ReceiptPage, "inventory", "receipt");
