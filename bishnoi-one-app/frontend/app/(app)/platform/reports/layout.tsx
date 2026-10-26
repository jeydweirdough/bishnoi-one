import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";

export default async function ReportsLayout({ children }: { children: ReactNode }) {
  if (!(await getAccount()).isCompanyAdmin) redirect("/platform");
  return children;
}
