// Shown in /inbox's place the moment a link to it is clicked: the page's own title first.
import { ListSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <ListSkeleton title="Lead inbox" columns={2} rows={6} />;
}
