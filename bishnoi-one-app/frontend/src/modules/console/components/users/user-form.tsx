"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/modules/console/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/modules/console/platform/ui/field";
import { Subheading } from "@/src/modules/console/platform/ui/sheet";
import { addUser, updateUser, type UserPatch } from "@/src/modules/console/actions/users";
import { plural } from "@/src/modules/console/lib/words";
import type { Options, PlatformUserDetail } from "@/src/modules/console/lib/types";
import { companyApplications, type CompanyApp } from "@/src/modules/console/components/users/company-apps";

type AppPick = { on: boolean; role: string; isAppAdmin: boolean };

/**
 * Adding a platform user (with the applications their company has, each with
 * a role), or changing their particulars. Moving someone to another company
 * keeps only the applications the new one has, and says which go before saving.
 */
export function UserForm({
  companies,
  user,
  companyId: initialCompany = "",
  initialApps = [],
}: {
  companies: Options["companies"];
  user?: PlatformUserDetail;
  companyId?: string;
  initialApps?: CompanyApp[];
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [loadingApps, startLoading] = useTransition();
  const [companyId, setCompanyId] = useState(user?.companyId ?? initialCompany);
  const [apps, setApps] = useState<CompanyApp[] | null>(user ? null : initialApps);
  const [picks, setPicks] = useState<Record<string, AppPick>>({});
  const [values, setValues] = useState({ fullName: user?.fullName ?? "", email: user?.email ?? "", title: user?.title ?? "" });
  const [isCompanyAdmin, setCompanyAdmin] = useState(user?.isCompanyAdmin ?? false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (k: keyof typeof values) => (e: { target: { value: string } }) => setValues({ ...values, [k]: e.target.value });
  const moving = Boolean(user && companyId !== user.companyId);
  // The applications they'd lose by moving: the ones the new company hasn't got.
  const losing = user && moving && apps ? user.applications.filter((g) => !apps.some((a) => a.id === g.applicationId)) : [];

  function chooseCompany(id: string) {
    setCompanyId(id);
    setPicks({});
    setApps(null);
    if (!id || (user && id === user.companyId)) return;
    startLoading(async () => {
      const result = await companyApplications(id);
      if (result.ok) setApps(result.data);
      else toast.error(result.error);
    });
  }

  function submit() {
    start(async () => {
      const clean = (v: string) => v.trim() || null;
      if (user) {
        const change: UserPatch = {};
        if (values.fullName.trim() !== user.fullName) change.fullName = values.fullName.trim();
        if (values.email.trim() !== user.email) change.email = values.email.trim();
        if (clean(values.title) !== (user.title ?? null)) change.title = clean(values.title);
        if (isCompanyAdmin !== user.isCompanyAdmin) change.isCompanyAdmin = isCompanyAdmin;
        if (moving) change.companyId = companyId;
        if (Object.keys(change).length === 0) {
          router.push(`/platform/accounts/${user.id}`);
          return;
        }
        const result = await updateUser(user.id, change);
        if (result.ok) {
          const n = result.data.withdrawnApplications;
          toast.success("Changes saved", { description: n ? `${plural(n, "application")} removed with the company change.` : values.fullName.trim() });
          router.push(`/platform/accounts/${user.id}`);
          return;
        }
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      const result = await addUser({
        companyId,
        fullName: values.fullName.trim(),
        email: values.email.trim(),
        title: clean(values.title),
        isCompanyAdmin,
        applications: Object.entries(picks)
          .filter(([, p]) => p.on)
          .map(([applicationId, p]) => ({ applicationId, role: clean(p.role), isAppAdmin: p.isAppAdmin })),
      });
      if (result.ok) {
        toast.success("User added", { description: result.data.fullName });
        router.push(`/platform/accounts/${result.data.id}`);
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  const pick = (id: string): AppPick => picks[id] ?? { on: false, role: "", isAppAdmin: false };
  const setPick = (id: string, change: Partial<AppPick>) => setPicks({ ...picks, [id]: { ...pick(id), ...change } });
  const companyName = companies.find((c) => c.id === companyId)?.name;

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-7"
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field
          label="Company"
          error={fields.companyId}
          hint={user ? "Changing company keeps only the applications assigned to the new company." : "The company the user belongs to."}
          className="sm:col-span-2"
        >
          {(p) => (
            <Select {...p} value={companyId} onChange={(e) => chooseCompany(e.target.value)} required>
              {!companyId && <option value="">Select a company</option>}
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.status === "suspended" ? " (suspended)" : ""}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {moving && losing.length > 0 && (
          <p role="status" className="rounded-[14px] bg-danger-tint px-3 py-2 text-meta text-danger sm:col-span-2">
            {companyName} doesn&apos;t have {losing.map((g) => g.name).join(", ")}. {user?.fullName} will lose {losing.length === 1 ? "it" : "them"} with the move.
          </p>
        )}
        <Field label="Full name" error={fields.fullName}>
          {(p) => <Input {...p} value={values.fullName} onChange={set("fullName")} autoFocus={!user && Boolean(companyId)} required />}
        </Field>
        <Field label="Email" error={fields.email}>
          {(p) => <Input {...p} type="email" inputMode="email" autoCapitalize="none" value={values.email} onChange={set("email")} required />}
        </Field>
        <Field label="Title" optional error={fields.title} hint="Job title, e.g. Pharmacist.">
          {(p) => <Input {...p} value={values.title} onChange={set("title")} />}
        </Field>
        <label className="flex cursor-pointer items-start gap-2.5 self-end pb-1 text-sm text-ink">
          <input type="checkbox" className="mt-0.5 size-4 accent-hema" checked={isCompanyAdmin} onChange={(e) => setCompanyAdmin(e.target.checked)} />
          <span>
            Company admin
            <span className="block text-meta text-ink-3">Manages the company&apos;s users and access.</span>
          </span>
        </label>
      </div>

      {!user && (
        <fieldset className="space-y-2">
          <legend className="mb-1">
            <Subheading>Applications</Subheading>
          </legend>
          {!companyId ? (
            <p className="text-meta text-ink-3">Select the company first: users can only be given its assigned applications.</p>
          ) : loadingApps || apps === null ? (
            <p className="text-meta text-ink-3">Looking up {companyName}&apos;s applications…</p>
          ) : apps.length === 0 ? (
            <p className="text-meta text-ink-3">{companyName} has no applications yet. Give it some on its Applications tab, then come back.</p>
          ) : (
            <ul className="divide-y divide-rule rounded-[18px] border border-rule" role="list">
              {apps.map((a) => {
                const p = pick(a.id);
                return (
                  <li key={a.id} className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5">
                    <label className="inline-flex min-w-[8rem] cursor-pointer items-center gap-2 text-sm font-semibold text-ink">
                      <input type="checkbox" className="size-4 accent-hema" checked={p.on} onChange={(e) => setPick(a.id, { on: e.target.checked })} />
                      {a.name}
                    </label>
                    {p.on && (
                      <>
                        <label className="min-w-0 flex-1">
                          <span className="sr-only">Role in {a.name}</span>
                          <Input value={p.role} placeholder={`Role in ${a.name} (optional)`} onChange={(e) => setPick(a.id, { role: e.target.value })} maxLength={60} />
                        </label>
                        <label className="inline-flex cursor-pointer items-center gap-2 text-meta text-ink-2">
                          <input type="checkbox" className="size-4 accent-hema" checked={p.isAppAdmin} onChange={(e) => setPick(a.id, { isAppAdmin: e.target.checked })} />
                          Runs {a.name} for {companyName}
                        </label>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {fields.applications && <p className="text-meta text-danger">{fields.applications}</p>}
        </fieldset>
      )}

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending} disabled={moving && loadingApps}>
          {user ? (moving && losing.length > 0 ? "Change company and save" : "Save changes") : "Add user"}
        </Button>
        <LinkButton href={user ? `/platform/accounts/${user.id}` : initialCompany ? `/platform/companies/${initialCompany}?tab=users` : "/platform/accounts"} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
