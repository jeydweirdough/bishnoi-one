// Shown in /reports/[key]'s place the moment a link to it is clicked: the shape of the
// page it opens, so the data fills in where the eye already is.
import { ListSkeleton } from "@/src/modules/inventory/platform/ui/skeleton";

export default function Loading() {
  return <ListSkeleton figures={3} chart />;
}
