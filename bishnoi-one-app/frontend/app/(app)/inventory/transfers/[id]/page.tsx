// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { TransferPage } from "@/src/modules/inventory/screens/transfers";
import { withTrail } from "@/src/platform/ui/document-trail";

export const metadata = { title: "Transfer" };
export default withTrail(TransferPage, "inventory", "transfer");
