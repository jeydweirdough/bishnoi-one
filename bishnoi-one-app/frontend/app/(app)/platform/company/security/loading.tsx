// Shown the moment a link here is clicked: the page's shape at once, the data filling in where the eye already is.
import { ListSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <ListSkeleton title="Security" figures={3} columns={4} />;
}
