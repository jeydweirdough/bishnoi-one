// Shown in /companies/find's place the moment a link to it is clicked: the page's own title first.
import { FormSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <FormSkeleton title="Find leads with AI" sections={3} />;
}
