"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { findLookalikes, type Lookalike } from "@/src/modules/crm/actions/crm";

/**
 * Smart search while a new customer is typed in: customers like it already in
 * the CRM, in any division. Shown, never refused: one hospital can be a
 * customer of several divisions. Waits for a pause in typing before asking.
 */
export function Lookalikes({ name, phone, email }: { name: string; phone: string; email: string }) {
  const [found, setFound] = useState<Lookalike[]>([]);
  const asked = useRef(0);

  useEffect(() => {
    const ask = ++asked.current;
    const enough = name.trim().length >= 3 || phone.replace(/\D/g, "").length >= 7 || email.includes("@");
    const wait = setTimeout(
      async () => {
        const result = enough ? await findLookalikes(name, phone, email) : [];
        if (ask === asked.current) setFound(result);
      },
      enough ? 350 : 0,
    );
    return () => clearTimeout(wait);
  }, [name, phone, email]);

  if (found.length === 0) return null;
  return (
    <div role="status" className="mt-2 rounded-sheet border border-rule bg-bench px-3 py-2">
      <p className="text-meta font-medium text-ink">Also in the CRM:</p>
      <ul className="mt-1 space-y-0.5 text-sm">
        {found.map((c) => (
          <li key={c.id} className="min-w-0 truncate">
            {c.canOpen ? (
              <Link href={`/crm/customers/${c.id}`} target="_blank" className="font-medium text-ink hover:underline">
                {c.name}
              </Link>
            ) : (
              <span className="font-medium text-ink">{c.name}</span>
            )}
            <span className="text-ink-3">
              {" · "}
              {[c.teamName, c.owner ? `assigned to ${c.owner}` : null, c.city].filter(Boolean).join(" · ") || "another division's"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
