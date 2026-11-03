// Shown the moment Data clean-up is clicked: its shape at once.
import { ListSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <ListSkeleton title="Data clean-up" columns={3} />;
}
