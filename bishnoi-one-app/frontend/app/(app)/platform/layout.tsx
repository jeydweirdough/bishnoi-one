import type { ReactNode } from "react";
import { AdminConsoleFrame } from "@/src/one/admin-console/frame";

export default function AdminConsoleLayout({ children }: { children: ReactNode }) {
  return <AdminConsoleFrame>{children}</AdminConsoleFrame>;
}
