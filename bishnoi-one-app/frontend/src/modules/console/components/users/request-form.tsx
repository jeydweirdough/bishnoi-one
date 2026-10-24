"use client";

import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/console/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/modules/console/platform/ui/field";
import { requestAccess } from "@/src/modules/console/actions/users";
import type { Ref } from "@/src/modules/console/lib/types";

/**
 * Logging an access request on someone's behalf: they asked Support, or
 * wrote in. Any staff can; a Platform Admin decides it under Access.
 */
export function RequestAccess({
  userId,
  name,
  applications,
  companyApps,
}: {
  userId: string;
  name: string;
  /** Applications they don't have yet. */
  applications: Ref[];
  /** Which of those their company has: the rest need the company to get them first. */
  companyApps: string[];
}) {
  const [open, setOpen] = useState(false);
  const [appId, setAppId] = useState(applications[0]?.id ?? "");
  const [role, setRole] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pending, start] = useTransition();
  const first = name.split(" ")[0];

  if (applications.length === 0) return null;
  if (!open) {
    return (
      <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Log an access request for {first}
      </Button>
    );
  }

  function submit() {
    start(async () => {
      const result = await requestAccess({ identityId: userId, applicationId: appId, role: role.trim() || null, reason: reason.trim() || null });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Request logged", { description: "A Platform Admin reviews it under Access." });
      setOpen(false);
      setRole("");
      setReason("");
      setError(null);
      setFields({});
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-4 rounded-[18px] bg-bench/40 px-4 py-4"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Application"
          error={fields.applicationId}
          hint={appId && !companyApps.includes(appId) ? "Not yet assigned to their company; it must be assigned before the request can be approved." : undefined}
        >
          {(p) => (
            <Select {...p} value={appId} onChange={(e) => setAppId(e.target.value)} autoFocus>
              {applications.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Requested role" optional error={fields.role}>
          {(p) => <Input {...p} value={role} onChange={(e) => setRole(e.target.value)} maxLength={60} />}
        </Field>
        <Field label="Reason" optional error={fields.reason} className="sm:col-span-2">
          {(p) => <Textarea {...p} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />}
        </Field>
      </div>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" variant="primary" loading={pending} disabled={!appId}>
          Log request
        </Button>
        <Button size="sm" variant="quiet" onClick={() => setOpen(false)} disabled={pending}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
