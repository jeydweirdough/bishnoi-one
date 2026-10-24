import { redirect } from "next/navigation";

// Roles are made once, for every module, in People and access (decided 2026-10-23).
export default function RolesMovedPage() {
  redirect("/platform/access/roles");
}
