// Shown the moment a link here is clicked: the page's shape at once, the data filling in where the eye already is.
import { DashboardSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <DashboardSkeleton title="Home" figures={4} />;
}
