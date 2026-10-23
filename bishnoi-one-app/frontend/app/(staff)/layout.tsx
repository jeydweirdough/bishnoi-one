import type { ReactNode } from "react";
import { Brand } from "@/src/one/brand";

// The Platform console's frame (decided 2026-10-24): Bishnoi One's own staff,
// signed in with their staff account rather than a company's Bishnoi One
// account, so the bar names the console instead of a person's modules and companies.
export default function StaffLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-bench">
      <header className="sticky top-0 z-40 border-b border-rule bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[90rem] items-center gap-4 px-4 sm:px-6">
          <Brand />
          <span className="h-6 w-px bg-rule" aria-hidden />
          <span className="text-sm font-semibold text-ink">Platform console</span>
        </div>
      </header>
      {children}
    </div>
  );
}
