import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { AdminUserRow } from "@/src/platform/lib/types";

/**
 * A person's sign-in: their password and switching them off (or on) are kept once for every module
 * in Bishnoi One's People (R2, decided 2026-10-26), so here it says where, and how they stand.
 */
export function UserAccess({ user }: { user: AdminUserRow; isMe?: boolean }) {
  return (
    <div className="space-y-3 text-sm">
      <p className="text-ink-2">
        {user.isActive ? "Can sign in." : "Switched off: can't sign in."} Passwords and switching people off are done in People, once for every module.
      </p>
      <Link href="/platform/roles/people" className="inline-flex items-center gap-1.5 font-medium text-ink hover:underline">
        Open People
        <ArrowRight className="size-4" aria-hidden />
      </Link>
    </div>
  );
}
