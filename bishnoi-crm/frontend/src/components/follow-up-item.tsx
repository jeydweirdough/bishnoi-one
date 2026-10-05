"use client";

import { Check, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useOptimistic, useTransition } from "react";
import { toast } from "sonner";
import { SelectBox, useSelectionMaybe } from "@/src/platform/bulk/selection";
import { Flag } from "@/src/platform/ui/marks";
import { updateActivity } from "../actions/crm";
import { makeFormat } from "@/src/platform/lib/format";
import type { Bucket, Org } from "@/src/platform/lib/types";

export type FollowUpRow = {
  id: string;
  title: string;
  dueOn: string;
  bucket: Bucket | null;
  status: "open" | "done";
  customerId: string;
  customerName: string | null;
  /** Where the customer's page is (a company or a contact). */
  href?: string;
  place?: string; // "B&B · MD Telesales" or just the team
  assigneeName?: string | null;
  doneByName?: string | null;
  doneAt?: string | null;
  canEdit: boolean;
};

export function FollowUpItem({ row, today, org, showCustomer = true }: { row: FollowUpRow; today: string; org: Org; showCustomer?: boolean }) {
  const fmt = makeFormat(org);
  const [pending, start] = useTransition();
  // The tick shows the moment it's tapped; the server confirms behind it. If the
  // save fails, the transition ends and the tick falls back to what's stored.
  const [status, showStatus] = useOptimistic(row.status);
  const done = status === "done";
  const saving = row.id.startsWith("pending-");
  // On the follow-ups list, "Select" swaps the done tick for a checkbox, so the
  // two never sit side by side waiting to be mis-tapped.
  const selection = useSelectionMaybe();
  const selecting = Boolean(selection?.selecting && row.canEdit && !saving);
  const selected = selection?.isSelected(row.id) ?? false;
  const busy = selection?.busy.has(row.id) ?? false;

  function toggle() {
    const next = done ? "open" : "done";
    start(async () => {
      showStatus(next);
      // A follow-up is a task: done or not.
      const result = await updateActivity(row.id, { done: next === "done" });
      if (!result.ok) toast.error(result.error, { description: row.title });
      else if (next === "done") toast.success("Marked done", { description: row.title });
    });
  }

  const due = fmt.dueLabel(row.dueOn, today);
  const meta = [row.place, row.assigneeName && !done ? `for ${row.assigneeName}` : null].filter(Boolean).join(" · ");

  return (
    <li
      aria-busy={busy || undefined}
      className={`flex items-start gap-3 py-3 transition-opacity ${saving || busy ? "opacity-60" : ""} ${selected ? "-mx-5 bg-hema-tint/60 px-5" : ""}`}
    >
      {selecting ? (
        <span className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center">
          <SelectBox id={row.id} label={row.title} />
        </span>
      ) : row.canEdit && !saving ? (
        <button
          type="button"
          onClick={toggle}
          aria-busy={pending || undefined}
          aria-label={done ? `Reopen: ${row.title}` : `Mark done: ${row.title}`}
          // 24px to look at, 40px to hit: marking done is the most repeated tap in the app.
          className={`relative mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full border before:absolute before:-inset-2 ${
            done ? "border-ink bg-ink text-white" : "border-control text-transparent hover:border-hema hover:text-ink"
          }`}
        >
          <Check className="size-3.5" aria-hidden />
        </button>
      ) : (
        <span aria-hidden className="mt-0.5 size-6 shrink-0" />
      )}
      <div className="min-w-0 flex-1">
        <p className={`font-medium ${done ? "text-ink-3 line-through decoration-ink-3/60" : "text-ink"}`}>{row.title}</p>
        <p className="mt-0.5 text-meta text-ink-3">
          {showCustomer && row.customerName && (
            <>
              <Link
                href={row.href ?? `/companies/${row.customerId}`}
                className="font-medium text-ink hover:underline"
              >
                {row.customerName}
              </Link>
              {meta && " · "}
            </>
          )}
          {meta}
        </p>
      </div>
      <div className="shrink-0 pt-0.5 text-right text-meta">
        {saving ? (
          <span className="text-ink-3">Saving…</span>
        ) : done ? (
          <span className="inline-flex items-center gap-1 text-ink-3">
            {row.doneAt ? `${row.doneByName ? `${row.doneByName.split(" ")[0]}, ` : ""}${fmt.whenLabel(row.doneAt, today)}` : "Just now"}
            {row.canEdit && <RotateCcw className="size-3" aria-hidden />}
          </span>
        ) : row.bucket === "overdue" ? (
          <Flag letter="!">{due}</Flag>
        ) : (
          <span className={row.bucket === "today" ? "font-semibold text-ink" : "text-ink-2"}>{due}</span>
        )}
      </div>
    </li>
  );
}
