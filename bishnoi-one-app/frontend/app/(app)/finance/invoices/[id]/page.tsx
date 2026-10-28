// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { InvoicePage } from "@/src/modules/finance/screens/invoices";
import { withTrail } from "@/src/platform/ui/document-trail";

export const metadata = { title: "Invoice" };
export default withTrail(InvoicePage, "finance", "invoice");
