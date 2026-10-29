"use client";

import { Modal } from "antd";
import { PenLine } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { signForDelivery } from "@/src/modules/inventory/actions/inventory";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import type { Cleaned } from "@/src/platform/signature/clean";
import { CHECKER, DrawPad } from "@/src/platform/signature/pads";

// Proof of delivery (feature plan step 10): the customer signs on the device for what they received; their
// name and signature go on the delivery note. Signed once, it stays as signed.

export function SignForDelivery({ orderId, recipient }: { orderId: string; recipient: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [signature, setSignature] = useState<Cleaned | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function save() {
    if (name.trim().length < 2) return setError("Write the name of the person receiving it.");
    if (!signature) return setError("Ask them to sign in the box.");
    start(async () => {
      const r = await signForDelivery(orderId, name.trim(), signature.dataUrl);
      if (!r.ok) return setError(r.error);
      toast.success(`Signed for by ${name.trim()}`, { description: "Their signature is on the delivery note." });
      setOpen(false);
      router.refresh();
    });
  }

  return (
    <>
      <Button variant="primary" icon={<PenLine className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Customer signs for delivery
      </Button>
      <Modal open={open} title={`Received by ${recipient}`} onCancel={() => !pending && setOpen(false)} footer={null} width={640} destroyOnHidden>
        <div className="mt-3 space-y-4">
          <Field label="Name of the person receiving it">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus />}</Field>
          <DrawPad onChange={setSignature} />
          <FormError message={error} />
          <div className="flex gap-2">
            <Button variant="primary" loading={pending} onClick={save}>
              Save signature
            </Button>
            <Button variant="quiet" disabled={pending} onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

/** Who signed for it, and their signature, on the order page. */
export function ReceivedProof({ name, at, image }: { name: string; at: string; image: string | null }) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      {image && (
        <div className={`rounded-[3px] border border-rule px-4 py-2 ${CHECKER}`}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={image} alt={`${name}'s signature`} className="h-12 max-w-64 object-contain" />
        </div>
      )}
      <p className="text-sm text-ink-2">
        Received by <strong className="text-ink">{name}</strong>, {at}
      </p>
    </div>
  );
}
