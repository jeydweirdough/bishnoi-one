"use client";

import { Check, CheckCheck, X } from "lucide-react";
import { useEffect, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, Textarea } from "@/src/modules/finance/platform/ui/field";
import { approveEntries, decideEntry } from "@/src/modules/finance/ledger/actions";
import { BULK_FORM } from "@/src/modules/finance/ledger/types";

/** Approve several entries at once (decided 2026-10-22). Each entry's tick box sits on
 *  its card (`form={BULK_FORM}`); this bar counts them, selects all shown, and sends
 *  them. Each is still checked as if alone: never your own, and not one someone else
 *  has just decided, which come back named. Rejecting stays one at a time. */
export function ApproveSeveral() {
  const form = useRef<HTMLFormElement>(null);
  const [count, setCount] = useState(0);
  const [pending, start] = useTransition();
  const boxes = () => Array.from(form.current?.elements ?? []).filter((el): el is HTMLInputElement => el instanceof HTMLInputElement && el.name === "ids");
  const recount = () => setCount(boxes().filter((b) => b.checked).length);

  useEffect(() => {
    const changed = (e: Event) => (e.target as HTMLInputElement | null)?.form === form.current && recount();
    document.addEventListener("change", changed);
    return () => document.removeEventListener("change", changed);
  }, []);

  function all() {
    const every = boxes();
    const on = every.some((b) => !b.checked);
    every.forEach((b) => (b.checked = on));
    recount();
  }

  function send() {
    const ids = boxes().filter((b) => b.checked).map((b) => b.value);
    start(async () => {
      const r = await approveEntries(ids);
      if (!r.ok) return void toast.error(r.error);
      const { approved, skipped } = r.data;
      const done = `${approved.length} ${approved.length === 1 ? "entry" : "entries"} approved`;
      if (skipped.length) toast.warning(done, { description: skipped.map((s) => `${s.number ?? "An entry"}: ${s.reason}`).join(" "), duration: 12000 });
      else toast.success(done, { description: "They now count in the books." });
      boxes().forEach((b) => (b.checked = false));
      setCount(0);
    });
  }

  return (
    <form ref={form} id={BULK_FORM} onSubmit={(e) => (e.preventDefault(), send())} className="mb-3 flex flex-wrap items-center gap-2 rounded-[3px] border border-rule bg-sheet px-4 py-2.5">
      <span className="text-meta text-ink-2">Tick the entries to approve, or</span>
      <Button type="button" size="sm" variant="quiet" onClick={all}>
        Select all shown
      </Button>
      <Button type="submit" size="sm" variant="primary" loading={pending} disabled={count === 0} icon={<CheckCheck className="size-4" aria-hidden />}>
        Approve selected{count ? ` (${count})` : ""}
      </Button>
    </form>
  );
}

/** Approve a journal entry waiting for approval, or reject it with a reason the
 *  person who posted it is told. If someone else decided it a moment earlier, the
 *  message says who and when, and the page shows the entry as it now stands. */
export function DecideEntry({ id, number }: { id: string; number: string }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function send(decision: "approve" | "reject") {
    if (decision === "reject" && !reason.trim()) return setError("Enter the reason for rejection.");
    setError(null);
    start(async () => {
      const result = await decideEntry(id, decision, decision === "reject" ? reason.trim() : null);
      // A toast, not the form's error line: the page is redrawn, and this form goes once the entry is decided.
      if (!result.ok) return void toast.error(result.error);
      toast.success(decision === "approve" ? `${number} approved` : `${number} rejected`, {
        description: decision === "approve" ? "It now counts in the books." : "Whoever posted it is told why.",
      });
    });
  }

  if (rejecting) {
    return (
      <div className="mt-2 w-full space-y-2 sm:max-w-sm">
        <Field label="Reason for rejection" hint="Whoever posted it sees this, and posts a corrected entry.">
          {(p) => <Textarea {...p} rows={2} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />}
        </Field>
        <FormError message={error} />
        <div className="flex gap-2">
          <Button variant="danger" size="sm" loading={pending} onClick={() => send("reject")}>
            Reject
          </Button>
          <Button variant="quiet" size="sm" disabled={pending} onClick={() => (setRejecting(false), setError(null))}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-2">
      <Button variant="primary" size="sm" loading={pending} icon={<Check className="size-4" aria-hidden />} onClick={() => send("approve")}>
        Approve
      </Button>
      <Button size="sm" disabled={pending} icon={<X className="size-4" aria-hidden />} onClick={() => setRejecting(true)}>
        Reject
      </Button>
    </div>
  );
}
