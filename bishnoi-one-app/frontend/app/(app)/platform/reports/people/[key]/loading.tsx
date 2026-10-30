// Shown the moment a report is clicked: its shape at once, the rows filling in where the eye already is.
import { ListSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <ListSkeleton title="Report" columns={6} />;
}
