// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { default as QuotePage } from "@/src/modules/crm/screens/quote";
import { withTrail } from "@/src/platform/ui/document-trail";

export default withTrail(QuotePage, "crm", "quote");
