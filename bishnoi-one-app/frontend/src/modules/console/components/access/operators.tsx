"use client";

import { Power, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { findAccounts, setOperator, type Operator } from "@/src/modules/console/actions/operators";
import { Button } from "@/src/platform/ui/button";
import { SearchInput } from "@/src/platform/ui/field";
import { Empty, Sheet } from "@/src/platform/ui/sheet";

// Operators (feature plan step 5): Bishnoi One's own people, a switch on their account. They see
// the Operations area and are administrator at every company; everyone else sees only their company.

export function OperatorsList({ operators, meEmail, canChange }: { operators: Operator[]; meEmail: string; canChange: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Operator[] | null>(null);

  function search(value: string) {
    if (value.trim().length < 2) return setFound(null);
    start(async () => {
      const r = await findAccounts(value.trim());
      if (!r.ok) return void toast.error(r.error);
      setFound(r.data);
    });
  }

  function flip(a: Operator, on: boolean) {
    start(async () => {
      const r = await setOperator(a.id, on);
      if (!r.ok) return void toast.error(r.error);
      toast.success(on ? `${a.fullName} is an operator` : `${a.fullName} is no longer an operator`);
      setFound(null);
      setQ("");
      router.refresh();
    });
  }

  return (
    <div className="space-y-4">
      {canChange && (
        <Sheet className="px-5 py-4">
          <p className="mb-2 text-sm font-medium text-ink">Make someone an operator</p>
          <div className="max-w-md">
            <SearchInput placeholder="Find an account by name or email" allowClear value={q} loading={busy} onChange={(e) => setQ(e.target.value)} onSearch={search} />
          </div>
          {found && (
            found.length === 0 ? (
              <p className="mt-2 text-meta text-ink-3">No account matches. They need a Bishnoi One account first: a company adds them on People.</p>
            ) : (
              <ul className="mt-2 divide-y divide-rule">
                {found.map((a) => (
                  <li key={a.id} className="flex items-center gap-3 py-2">
                    <span className="min-w-0 flex-1 truncate text-sm">
                      <span className="font-medium text-ink">{a.fullName}</span> <span className="text-ink-3">{a.email}</span>
                    </span>
                    <Button size="sm" icon={<UserPlus className="size-4" aria-hidden />} onClick={() => flip(a, true)} disabled={busy}>
                      Make operator
                    </Button>
                  </li>
                ))}
              </ul>
            )
          )}
        </Sheet>
      )}
      <Sheet className="px-5 pt-4 pb-2">
        {operators.length === 0 ? (
          <Empty icon="people" title="No operators">
            Someone must run Bishnoi One: make an account an operator.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {operators.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-3">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-ink">
                    {a.fullName}
                    {a.email === meEmail && <span className="ml-2 rounded-full bg-hema-tint px-1.5 text-stamp text-hema uppercase">You</span>}
                  </span>
                  <span className="block truncate text-meta text-ink-3">{a.email}</span>
                </span>
                {canChange && a.email !== meEmail && (
                  <Button size="sm" icon={<Power className="size-4" aria-hidden />} onClick={() => flip(a, false)} disabled={busy}>
                    Remove operator
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}
