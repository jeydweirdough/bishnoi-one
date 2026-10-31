// Finance's settings in the Admin Console (2026-10-31): company administrators only. The pages are
// Finance's own and talk to its API (modules.ts borrowedOf).
import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";

export default async function Layout({ children }: { children: ReactNode }) {
  if (!(await getAccount()).isCompanyAdmin) redirect("/finance");
  return children;
}
