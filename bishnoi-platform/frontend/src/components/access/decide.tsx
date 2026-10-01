"use client";

import { useId, useState } from "react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Textarea } from "@/src/platform/ui/field";
import { decideRequest } from "../../actions/users";
import type { AccessRequest } from "../../lib/types";

/** Approve and Decline beside an access request, each asking first with room for a note. */
export function Decide({ request, canApprove }: { request: AccessRequest; canApprove: boolean }) {
  const [note, setNote] = useState("");
  const who = request.user.name;
  const first = who.split(" ")[0];
  const noteField = <Note value={note} onChange={setNote} />;

  async function decide(approve: boolean) {
    const result = await decideRequest(request.id, approve, note.trim() || null);
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    toast.success(approve ? "Access given" : "Request declined", { description: `${request.application.name} · ${who}` });
    setNote("");
  }

  return (
    <span className="flex flex-wrap gap-2">
      {canApprove && (
        <ConfirmButton
          label="Approve"
          triggerVariant="primary"
          triggerSize="sm"
          triggerTitle={`Give ${request.application.name} to ${who}`}
          danger={false}
          title={`Give ${request.application.name} to ${who}?`}
          body={
            <>
              <p>
                {first} can use {request.application.name}
                {request.role ? ` as ${request.role}` : ""} from now on. You can change their role or withdraw it from their page.
              </p>
              {noteField}
            </>
          }
          confirmLabel="Approve"
          onConfirm={() => decide(true)}
        />
      )}
      <ConfirmButton
        label="Decline"
        triggerSize="sm"
        triggerTitle={`Decline ${who}'s request for ${request.application.name}`}
        title={`Decline ${who}'s request?`}
        body={
          <>
            <p>
              {first} doesn&apos;t get {request.application.name}. The request is kept, marked declined.
            </p>
            {noteField}
          </>
        }
        confirmLabel="Decline"
        onConfirm={() => decide(false)}
      />
    </span>
  );
}

function Note({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const id = useId();
  return (
    <label htmlFor={id} className="mt-3 block">
      <span className="mb-1 block text-meta font-medium text-ink-2">
        Note <span className="font-normal text-ink-3">(optional, kept with the request)</span>
      </span>
      <Textarea id={id} rows={2} maxLength={500} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
