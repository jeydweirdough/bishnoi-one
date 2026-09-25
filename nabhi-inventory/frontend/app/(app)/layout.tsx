// The signed-in frame: the same sidebar every Nabhi app wears, with how many
// things wait on this person beside each place they work in.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { api } from "@/src/platform/lib/api";
import type { Alert } from "@/src/lib/types";

async function waiting(): Promise<Record<string, number>> {
  try {
    // The API only lists what this person's role may act on.
    const alerts = await api.get<Alert[]>("/inventory/alerts");
    return Object.fromEntries(alerts.map((a) => [a.key, a.count]));
  } catch {
    // Counts are a help, not the page: without them the sidebar still works.
    return {};
  }
}

export default async function Layout({ children }: { children: ReactNode }) {
  return <ShellLayout waiting={await waiting()}>{children}</ShellLayout>;
}
