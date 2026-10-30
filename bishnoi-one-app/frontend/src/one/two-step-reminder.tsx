import Link from "next/link";
import { ShieldAlert } from "lucide-react";

/**
 * The reminder for those who run a company (or Bishnoi One) without two-step sign-in (decided 2026-10-30:
 * it's optional, so nobody is stopped, but the reminder stays on every page until it's set up).
 */
export function TwoStepReminder() {
  return (
    <div role="status" className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b border-promo bg-promo-tint px-4 py-1.5 text-meta text-promo-ink">
      <ShieldAlert className="size-4 shrink-0" aria-hidden />
      <span>You run this company without two-step sign-in: a stolen password alone could open your account.</span>
      <Link href="/platform/account#two-step" className="font-semibold underline">
        Set it up now
      </Link>
    </div>
  );
}
