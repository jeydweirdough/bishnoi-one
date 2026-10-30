"use client";

import { Power, UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { addOperator, findPeople, setOperator, type FoundPerson, type Operator } from "@/src/modules/console/actions/operators";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, PasswordInput, SearchInput } from "@/src/platform/ui/field";
import { Empty, Sheet } from "@/src/platform/ui/sheet";

// Operators (feature plan step 5): Bishnoi One's own people. They see the Operations area and work in
// every company. One email, one account (decided 2026-10-29): an operator has an email of their own,
// never one a company's person signs in with, and only operators add operators.

/** A new operator: their own email, their name, and a first password to pass on to them. */
function AddOperator({ onDone }: { onDone: () => void }) {
  const [busy, start] = useTransition();
  const [form, setForm] = useState({ email: "", fullName: "", password: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function submit() {
    start(async () => {
      const r = await addOperator({ email: form.email.trim(), fullName: form.fullName.trim(), password: form.password });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success(`${r.data.fullName} is an operator`, { description: `They sign in as ${r.data.email} with the password you gave.` });
      setForm({ email: "", fullName: "", password: "" });
      setFields({});
      setError(null);
      onDone();
    });
  }

  return (
    <form noValidate onSubmit={(e) => (e.preventDefault(), submit())}>
      <p className="mb-1 text-sm font-medium text-ink">Add an operator</p>
      <p className="mb-3 text-meta text-ink-3">With an email of their own, such as name@bishnoione.ai. An email a company&apos;s person signs in with can&apos;t be an operator&apos;s too.</p>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Name" error={fields.fullName}>
          {(p) => <Input {...p} value={form.fullName} onChange={(e) => setForm({ ...form, fullName: e.target.value })} maxLength={120} />}
        </Field>
        <Field label="Email" error={fields.email}>
          {(p) => <Input {...p} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} maxLength={254} />}
        </Field>
        <Field label="First password" hint="Pass it on; they change it." error={fields.password}>
          {(p) => <PasswordInput {...p} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" />}
        </Field>
      </div>
      <FormError message={error} />
      <div className="mt-3">
        <Button type="submit" size="sm" icon={<UserPlus className="size-4" aria-hidden />} loading={busy}>
          Add operator
        </Button>
      </div>
    </form>
  );
}

export function OperatorsList({ operators, meEmail, canChange }: { operators: Operator[]; meEmail: string; canChange: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();

  function remove(a: Operator) {
    start(async () => {
      const r = await setOperator(a.id, false);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`${a.fullName} is no longer an operator`);
      router.refresh();
    });
  }

  return (
    <div className="space-y-4">
      {canChange && (
        <Sheet className="px-5 py-4">
          <AddOperator onDone={() => router.refresh()} />
        </Sheet>
      )}
      <Sheet className="px-5 pt-4 pb-2">
        {operators.length === 0 ? (
          <Empty icon="people" title="No operators">
            Someone must run Bishnoi One: add an operator.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {operators.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-3">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-ink">
                    {a.fullName}
                    {a.email === meEmail && <span className="ml-2 rounded-full bg-hema-tint px-1.5 text-stamp text-hema uppercase">You</span>}
                  </span>
                  <span className="block truncate text-meta text-ink-3">{a.email}</span>
                </span>
                {canChange && a.email !== meEmail && (
                  <Button size="sm" icon={<Power className="size-4" aria-hidden />} onClick={() => remove(a)} disabled={busy}>
                    Remove operator
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}

/** Find a person (Operations): any email at any company, with where it belongs. */
export function FindPerson() {
  const [busy, start] = useTransition();
  const [q, setQ] = useState("");
  const [found, setFound] = useState<FoundPerson[] | null>(null);

  function search(value: string) {
    if (value.trim().length < 2) return setFound(null);
    start(async () => {
      const r = await findPeople(value.trim());
      if (!r.ok) return void toast.error(r.error);
      setFound(r.data);
    });
  }

  return (
    <div className="space-y-4">
      <div className="max-w-md">
        <SearchInput placeholder="Name or email" allowClear autoFocus value={q} loading={busy} onChange={(e) => setQ(e.target.value)} onSearch={search} />
      </div>
      {found && (
        <Sheet className="px-5 pt-2 pb-2">
          {found.length === 0 ? (
            <Empty icon="people" title="Nobody matches" source="Each company's People, and Operators." />
          ) : (
            <ul className="divide-y divide-rule">
              {found.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-3 py-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-ink">{a.fullName}</span>
                    <span className="block truncate text-meta text-ink-3">{a.email}</span>
                  </span>
                  <span className="flex flex-wrap gap-1.5 text-meta">
                    {a.isOperator && <span className="rounded-full bg-hema-tint px-2 py-0.5 text-hema">Operator</span>}
                    {a.status !== "active" && <span className="rounded-full bg-danger-tint px-2 py-0.5 text-danger">Account suspended</span>}
                    {a.memberships.map((m) => (
                      <Link
                        key={m.id}
                        href={`/operations/companies/${m.companyId}`}
                        title={m.offDomain ? "Not at the company's email domain: can't sign in until it's changed" : m.status === "active" ? undefined : "Suspended there"}
                        className={`rounded-full border px-2 py-0.5 hover:border-hema ${m.status === "active" ? "border-rule-strong text-ink" : "border-rule text-ink-3 line-through"}`}
                      >
                        {m.company}
                        {m.isCompanyAdmin && " · administrator"}
                        {m.offDomain && " · email to change"}
                      </Link>
                    ))}
                    {!a.isOperator && a.memberships.length === 0 && <span className="text-ink-3">No company</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
      )}
    </div>
  );
}
