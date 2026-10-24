// Shown in /companies/[id]/quotes/new's place the moment a link to it is clicked: the shape of the
// page it opens, so the data fills in where the eye already is.
import { FormSkeleton } from "@/src/platform/ui/skeleton";

export default function Loading() {
  return <FormSkeleton sections={1} summary lines />;
}
