"use client";

import { Check, Copy } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { changeMe } from "../../actions/platform";

/**
 * Your name and email, changed here; a new email (what you sign in with)
 * asks for your password. Your account's ID beside them, to copy for Support.
 */
export function DetailsForm({ id, no, fullName, email, role }: { id: string; no: number | null; fullName: string; email: string; role: string }) {
  const [v, setV] = useState({ fullName, email, password: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, start] = useTransition();
  const newEmail = v.email.trim().toLowerCase() !== email;
  const dirty = v.fullName.trim() !== fullName || newEmail;

  function save(e: React.FormEvent) {
    e.preventDefault();
    if (!v.fullName.trim()) return setFields({ fullName: "Type your name." });
    start(async () => {
      const r = await changeMe({ fullName: v.fullName.trim(), email: v.email.trim(), ...(newEmail ? { currentPassword: v.password } : {}) });
      if (!r.ok) {
        setError(r.fields && Object.keys(r.fields).length ? null : r.error);
        setFields(r.fields ?? {});
        return;
      }
      setFields({});
      setError(null);
      setV((x) => ({ ...x, password: "" }));
      toast.success("Your details are saved", { description: newEmail ? "Sign in with your new email from now on." : undefined });
    });
  }

  async function copy() {
    await navigator.clipboard?.writeText(id).catch(() => undefined);
    setCopied(true);
  }

  return (
    <form onSubmit={save} className="mt-3 space-y-4">
      <Field label="Name" error={fields.fullName}>
        {(p) => <Input {...p} value={v.fullName} onChange={(e) => setV({ ...v, fullName: e.target.value })} maxLength={120} autoComplete="name" />}
      </Field>
      <Field label="Email" error={fields.email} hint="What you sign in with.">
        {(p) => <Input {...p} type="email" value={v.email} onChange={(e) => setV({ ...v, email: e.target.value })} maxLength={254} autoComplete="email" />}
      </Field>
      {newEmail && (
        <Field label="Your current password" error={fields.currentPassword} hint="To change the email you sign in with.">
          {(p) => <PasswordInput {...p} value={v.password} onChange={(e) => setV({ ...v, password: e.target.value })} autoComplete="current-password" />}
        </Field>
      )}
      <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-y-2 text-sm">
        <span className="text-ink-3">Role</span>
        <span className="text-ink">{role}</span>
        {no && (
          <>
            <span className="text-ink-3">Number</span>
            <span className="text-ink tabular-nums">{no}</span>
          </>
        )}
        <span className="text-ink-3">Account ID</span>
        <span className="flex min-w-0 items-center gap-2">
          <code className="truncate text-meta text-ink-2">{id}</code>
          <button type="button" onClick={copy} className="shrink-0 text-ink-3 hover:text-hema" title="Copy your account ID" aria-label="Copy your account ID">
            {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
          </button>
        </span>
      </div>
      <FormError message={error} />
      <Button type="submit" variant="primary" loading={pending} disabled={!dirty}>
        Save your details
      </Button>
    </form>
  );
}
