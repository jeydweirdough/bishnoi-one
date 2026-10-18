"use client";

import { UserPlus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { useCan } from "./can";
import { AddCustomer } from "./forms";
import { QuickAddWindow } from "./quick-add";

/**
 * A customer picker with nothing to pick: says why, and offers to add them
 * there and then. The new customer is picked in the field, so the call, deal
 * or email being written isn't left.
 */
export function CustomerNotFound({
  typed,
  loading = false,
  none = false,
  onAdded,
  what = "customer",
}: {
  /** What was searched for. */
  typed: string;
  loading?: boolean;
  /** No customers at all yet. */
  none?: boolean;
  onAdded: (customer: { id: string; name: string }) => void;
  what?: string;
}) {
  const mayAdd = useCan()("customers.create");
  const [open, setOpen] = useState(false);
  if (loading) return <p className="px-1 py-3 text-meta text-ink-3">Looking…</p>;
  const empty = none && !typed;
  return (
    <div className="space-y-3 px-1 py-4 text-center">
      <p className="text-meta text-ink-3">{empty ? `You have no ${what}s yet. Add the first one here.` : typed ? <>No {what} called &ldquo;{typed}&rdquo; yet.</> : `Type a ${what}'s name to find them.`}</p>
      {(empty || typed) &&
        (mayAdd ? (
          <Button
            variant="primary"
            size="sm"
            icon={<UserPlus className="size-4" aria-hidden />}
            // Kept from closing the list before the click lands.
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setOpen(true)}
          >
            {empty ? `Add your first ${what}` : `Add \u201c${typed}\u201d as a ${what}`}
          </Button>
        ) : (
          <p className="text-meta text-ink-3">Ask someone who can add customers to add them.</p>
        ))}
      <QuickAddWindow open={open} title={`New ${what}`} onClose={() => setOpen(false)}>
        {(done) => <AddCustomer initialName={typed} onAdded={onAdded} done={done} />}
      </QuickAddWindow>
    </div>
  );
}
