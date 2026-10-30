// The sign-in steps have no shape to show before they know who you are: the 4-dot loader (decided 2026-10-30).
import { DotsPanel } from "@/src/platform/ui/dots";

export default function Loading() {
  return <DotsPanel label="Getting your account ready…" className="min-h-dvh bg-white" />;
}
