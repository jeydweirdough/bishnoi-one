"use client";

import { Alert, Modal } from "antd";
import { Check, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Textarea } from "@/src/platform/ui/field";
import { decideMaterialRequest } from "@/src/modules/crm/actions/materials";

/**
 * Approve or reject a request to give out promotional materials, beside it.
 * Approving takes one click; rejecting asks why, so Admin and the marketing
 * assistant know what to change.
 */
export function RequestDecision({ id, title }: { id: string; title: string }) {
  const router = useRouter();
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function decide(outcome: "approved" | "rejected") {
    start(async () => {
      const r = await decideMaterialRequest(id, outcome, note.trim() || null);
      if (!r.ok) {
        setError(r.fields?.note ?? r.error);
        if (outcome === "approved") toast.error(r.error);
        return;
      }
      toast.success(outcome === "approved" ? "Approved: Admin can give it out" : "Rejected", { description: title });
      setRejecting(false);
      setNote("");
      router.refresh();
    });
  }

  return (
    <>
      <div className="flex flex-wrap justify-end gap-2">
        <Button size="sm" icon={<X className="size-3.5" aria-hidden />} onClick={() => setRejecting(true)} aria-haspopup="dialog" disabled={pending}>
          Reject
        </Button>
        <Button size="sm" variant="primary" icon={<Check className="size-3.5" aria-hidden />} onClick={() => decide("approved")} loading={pending && !rejecting}>
          Approve
        </Button>
      </div>
      <Modal
        open={rejecting}
        title="Reject request"
        onCancel={() => {
          setRejecting(false);
          setError(null);
        }}
        width={460}
        destroyOnHidden
        footer={
          <div className="flex justify-end gap-2">
            <Button onClick={() => setRejecting(false)}>Cancel</Button>
            <Button variant="danger" onClick={() => decide("rejected")} loading={pending} disabled={!note.trim()}>
              Reject request
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-ink-2">{title}</p>
          <Field label="Reason" hint="Admin sees this with the request.">
            {(p) => <Textarea {...p} autoFocus value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />}
          </Field>
          {error && <Alert type="error" showIcon title={error} />}
        </div>
      </Modal>
    </>
  );
}
