import type { ReactNode } from "react";

// Every signed-in page of the one app. No bar across the top (decided
// 2026-10-24): each module's pages bring its sidebar, and at the top right its
// own actions, your modules and your account (src/one/one-actions.tsx), as
// before the one app. Pages with no sidebar use src/one/plain-frame.tsx.
export default function AppLayout({ children }: { children: ReactNode }) {
  return <div className="min-h-dvh bg-bench">{children}</div>;
}
