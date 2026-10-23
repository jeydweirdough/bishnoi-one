// Shown in /orders's place the moment a link to it is clicked: the shape of the
// page it opens, so the data fills in where the eye already is.
import { BoardSkeleton } from "@/src/modules/inventory/platform/ui/skeleton";

export default function Loading() {
  return <BoardSkeleton />;
}
