"use client";

import { CheckCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Textarea } from "@/src/platform/ui/field";
import { decideMaterial, type MaterialDecision } from "../actions/pharmacy";

type Outcome = MaterialDecision["outcome"];

const OUTCOMES: { value: Outcome; label: string }[] = [
  { value: "approved", label: "Approve" },
  { value: "returned", label: "Return for changes" },
  { value: "rejected", label: "Reject" },
];

const SUBMIT: Record<Outcome, string> = {
  approved: "Approve design",
  returned: "Return for changes",
  rejected: "Reject design",
};

/**
 * The pharmacist's decision on a design: approved for production, returned
 * with what to change (the marketing assistant sends a new version), or
 * rejected. Returning or rejecting needs comments; the API holds the same line.
 */
export function MaterialDecisionForm({ id, number }: { id: string; number: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [outcome, setOutcome] = useState<Outcome>("approved");
  const [comments, setComments] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  function submit() {
    start(async () => {
      const result = await decideMaterial(id, { outcome, comments: comments.trim() || null });
      if (result.ok) {
        toast.success(outcome === "approved" ? "Approved: Admin can produce it" : outcome === "returned" ? "Returned for changes" : "Rejected", { description: number });
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      <Choice name="outcome" legend="Decision" value={outcome} onChange={setOutcome} options={OUTCOMES} />
      <Field
        label="Comments"
        optional={outcome === "approved"}
        error={fields.comments}
        hint={outcome === "returned" ? "What to change: the marketing assistant sees this and sends a corrected version." : outcome === "rejected" ? "Why it can't be used." : undefined}
      >
        {(p) => <Textarea {...p} value={comments} onChange={(e) => setComments(e.target.value)} maxLength={4000} />}
      </Field>
      <FormError message={error} />
      <Button
        type="submit"
        variant={outcome === "rejected" ? "danger" : "primary"}
        loading={pending}
        icon={outcome === "approved" ? <CheckCheck className="size-4" aria-hidden /> : undefined}
      >
        {SUBMIT[outcome]}
      </Button>
    </form>
  );
}
