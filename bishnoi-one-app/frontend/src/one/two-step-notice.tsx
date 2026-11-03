import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { getAccount } from "@/src/platform/lib/account";

/** On a profile, for whoever hasn't two-step sign-in (2026-11-01, in place of the bar on every page). */
export function TwoStepNotice({ href = "/platform/account#two-step" }: { href?: string }) {
  return (
    <div role="status" className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-promo bg-promo-tint px-4 py-2.5 text-sm text-promo-ink">
      <ShieldAlert className="size-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1">Two-step sign-in is off: a stolen password alone could open your account.</span>
      <Link href={href} className="font-semibold underline">
        Set it up now
      </Link>
    </div>
  );
}

/** The notice on an app's own profile page, which doesn't otherwise read the account. */
export async function TwoStepOwed() {
  const account = await getAccount();
  return account.twoStep?.suggested ? <TwoStepNotice /> : null;
}
