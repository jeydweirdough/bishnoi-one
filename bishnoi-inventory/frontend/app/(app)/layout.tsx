// The signed-in frame: the same sidebar every Bishnoi One app wears, with how many
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

/** What isn't set up yet (a product with no price), for the sidebar's red counts. */
async function unset(): Promise<Record<string, number>> {
  return api.get<Record<string, number>>("/inventory/unset").catch(() => ({}));
}

export default async function Layout({ children }: { children: ReactNode }) {
  const [counts, missing] = await Promise.all([waiting(), unset()]);
  return (
    <ShellLayout waiting={counts} unset={missing}>
      {children}
    </ShellLayout>
  );
}
