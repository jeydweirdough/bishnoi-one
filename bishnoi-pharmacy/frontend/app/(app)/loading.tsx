// Shown in the page's place the moment a link is clicked, while the next page
// loads. The sidebar and everything around the page stay as they are.
import { PageSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <PageSkeleton />;
}
