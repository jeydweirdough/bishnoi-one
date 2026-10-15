// Shown in /transfers/map's place the moment a link to it is clicked: the shape of the
// page it opens, so the data fills in where the eye already is.
import { MapSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <MapSkeleton fields={false} />;
}
