"use client";

import { useRouter } from "next/navigation";
import { useId, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Textarea } from "@/src/platform/ui/field";
import { setBatchStatus } from "../actions/pharmacy";
import type { BatchStatus } from "../lib/types";

const ASK: Record<Exclude<BatchStatus, "available">, { title: string; body: string; confirm: string }> = {
  quarantined: {
    title: "Quarantine",
    body: "It's held back while it's looked into: nothing is dispensed or sold from it until it's released.",
    confirm: "Quarantine batch",
  },
  recalled: {
    title: "Recall",
    body: "Withdrawn for good. A recall is final: it's never dispensed or sold again. Take what's left off the shelf with a stock adjustment.",
    confirm: "Recall batch",
  },
};

/** A batch's own controls, on its row: hold it back, recall it, or release it. */
export function BatchActions({ id, lotNo, status }: { id: string; lotNo: string; status: BatchStatus }) {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [pending, start] = useTransition();
  const [target, setTarget] = useState<Exclude<BatchStatus, "available">>("quarantined");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (status === "recalled") return null;

  function run(next: BatchStatus, why: string | null) {
    start(async () => {
      const result = await setBatchStatus(id, next, why);
      if (result.ok) {
        toast.success(next === "available" ? `Lot ${lotNo} released` : `Lot ${lotNo} ${next}`);
        dialog.current?.close();
        setReason("");
        setError(null);
        router.refresh();
        return;
      }
      setError(result.fields?.reason ?? result.error);
      if (!dialog.current?.open) toast.error(result.error);
    });
  }

  function ask(next: Exclude<BatchStatus, "available">) {
    setTarget(next);
    setError(null);
    dialog.current?.showModal();
  }

  return (
    <span className="relative z-10 inline-flex flex-wrap justify-end gap-x-3 gap-y-1 text-meta">
      {status === "quarantined" ? (
        <button type="button" className="font-semibold text-hema hover:underline" disabled={pending} onClick={() => run("available", null)}>
          Release lot {lotNo}
        </button>
      ) : (
        <button type="button" className="font-semibold text-hema hover:underline" onClick={() => ask("quarantined")}>
          Quarantine
        </button>
      )}
      <button type="button" className="font-semibold text-danger hover:underline" onClick={() => ask("recalled")}>
        Recall
      </button>
      <dialog ref={dialog} aria-labelledby={titleId} className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-[3px] bg-sheet p-0 text-left shadow-lg backdrop:bg-ink/30">
        <form
          method="dialog"
          className="space-y-4 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            run(target, reason.trim() || null);
          }}
        >
          <h2 id={titleId} className="text-heading text-ink">
            {ASK[target].title} lot {lotNo}?
          </h2>
          <p className="text-sm text-ink-2">{ASK[target].body}</p>
          <Field label="Why" error={error ?? undefined}>
            {(p) => <Textarea {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} autoFocus />}
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="quiet" onClick={() => dialog.current?.close()}>
              Cancel
            </Button>
            <Button type="submit" variant={target === "recalled" ? "danger" : "primary"} loading={pending}>
              {ASK[target].confirm}
            </Button>
          </div>
        </form>
      </dialog>
    </span>
  );
}
