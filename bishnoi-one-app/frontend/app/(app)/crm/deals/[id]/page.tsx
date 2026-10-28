// The route. The screen is in src/, so it can be read on its own; the document trail (step 9) follows it.
import { default as DealPage } from "@/src/modules/crm/screens/deal";
export { generateMetadata } from "@/src/modules/crm/screens/deal";
import { withTrail } from "@/src/platform/ui/document-trail";

export default withTrail(DealPage, "crm", "deal");
