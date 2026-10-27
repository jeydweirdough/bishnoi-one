import { ArrowRight, Users } from "lucide-react";
import Link from "next/link";

// On every module's Users page (R2, decided 2026-10-26): people are added, given their role and the
// modules they open, given a password and switched off once, in Bishnoi One's People. A module's
// page keeps only what is its own about a person (an e-signature, a licence number, an employee ID).
export function PeopleNotice({ own }: { own?: string }) {
  return (
    <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl bg-mint px-4 py-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white text-sage-deep">
        <Users className="size-4" aria-hidden />
      </span>
      <p className="min-w-0 flex-1 text-sm text-ink">
        Add people, give roles and switch people off in one place for every module.
        {own && <span className="block text-meta text-ink-2">Here: {own}.</span>}
      </p>
      <Link href="/platform/roles/people" className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink px-3.5 text-sm font-medium text-white hover:bg-ink/85">
        Open People
        <ArrowRight className="size-4" aria-hidden />
      </Link>
    </div>
  );
}
