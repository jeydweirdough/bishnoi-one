"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/console/platform/ui/button";
import { ConfirmButton } from "@/src/modules/console/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/modules/console/platform/ui/field";
import { Empty } from "@/src/modules/console/platform/ui/sheet";
import { grantApplication, withdrawApplication } from "@/src/modules/console/actions/users";
import { ago, when } from "@/src/modules/console/lib/words";
import type { Grant, PlatformUserDetail } from "@/src/modules/console/lib/types";
import { ICON_BUTTON, ICON_TRIGGER_DANGER } from "@/src/modules/console/components/organizations/record-tools";
import { AdminStamp } from "@/src/modules/console/components/users/user-rows";

/**
 * A person's applications, each with its role and whether they run it, and
 * the change and withdraw controls beside it. Below, giving them another of
 * their company's applications.
 */
export function Grants({ user, canChange }: { user: PlatformUserDetail; canChange: boolean }) {
  const [giving, setGiving] = useState(false);
  const first = user.fullName.split(" ")[0];
  return (
    <div>
      {user.applications.length === 0 && !giving ? (
        <Empty title={`${first} has no applications`} icon="apps">
          {canChange
            ? user.canBeGiven.length
              ? "Grant access to one of their company's applications with “Grant access”."
              : `${user.companyName ?? "Their company"} has no assigned applications. Assign them on its Applications tab first.`
            : "A Platform Admin grants application access. Log an access request for them below."}
        </Empty>
      ) : (
        <ul className="divide-y divide-rule" role="list">
          {user.applications.map((g) => (
            <GrantRow key={g.applicationId} grant={g} user={user} canChange={canChange} />
          ))}
        </ul>
      )}
      {canChange &&
        (giving ? (
          <GrantForm user={user} onDone={() => setGiving(false)} />
        ) : (
          user.canBeGiven.length > 0 && (
            <div className="border-t border-rule px-5 py-3">
              <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setGiving(true)}>
                Grant access
              </Button>
            </div>
          )
        ))}
    </div>
  );
}

function GrantRow({ grant, user, canChange }: { grant: Grant; user: PlatformUserDetail; canChange: boolean }) {
  const [editing, setEditing] = useState(false);
  const first = user.fullName.split(" ")[0];
  if (editing) return <GrantForm user={user} grant={grant} onDone={() => setEditing(false)} />;
  return (
    <li className="px-5 py-3">
      <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold text-ink">{grant.name}</span>
        {grant.isAppAdmin && <AdminStamp label="App admin" />}
        {canChange && (
          <span className="flex items-center">
            <button suppressHydrationWarning
              type="button"
              className={ICON_BUTTON}
              title={`Change ${first}'s role in ${grant.name}`}
              aria-label={`Change ${first}'s role in ${grant.name}`}
              onClick={() => setEditing(true)}
            >
              <Pencil className="size-4" aria-hidden />
            </button>
            <ConfirmButton
              label={<span className="sr-only">Withdraw {grant.name} from {first}</span>}
              icon={<Trash2 className="size-4" aria-hidden />}
              triggerTitle={`Revoke ${first}'s access to ${grant.name}`}
              triggerVariant="quiet"
              triggerSize="sm"
              triggerClassName={ICON_TRIGGER_DANGER}
              title={`Revoke ${user.fullName}'s access to ${grant.name}?`}
              body={`${first} can't use ${grant.name} any more${grant.role ? `, and their role (${grant.role}) is removed` : ""}. Access can be granted again later.`}
              confirmLabel="Revoke access"
              onConfirm={async () => {
                const result = await withdrawApplication(user.id, grant.applicationId);
                if (!result.ok) {
                  toast.error(result.error);
                  return false;
                }
                toast.success("Access revoked", { description: `${grant.name} · ${user.fullName}` });
              }}
            />
          </span>
        )}
      </span>
      <span className="block text-meta text-ink-3">
        {grant.role ? <span className="text-ink-2">{grant.role}</span> : "No role assigned"} · granted by {grant.grantedBy}{" "}
        <time dateTime={grant.grantedAt} title={when(grant.grantedAt)}>
          {ago(grant.grantedAt)}
        </time>
      </span>
    </li>
  );
}

/** Giving an application (grant absent), or changing the role and admin mark of one they have. */
function GrantForm({ user, grant, onDone }: { user: PlatformUserDetail; grant?: Grant; onDone: () => void }) {
  const [appId, setAppId] = useState(grant?.applicationId ?? user.canBeGiven[0]?.id ?? "");
  const [role, setRole] = useState(grant?.role ?? "");
  const [isAppAdmin, setAppAdmin] = useState(grant?.isAppAdmin ?? false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pending, start] = useTransition();
  const appName = grant?.name ?? user.canBeGiven.find((a) => a.id === appId)?.name ?? "it";
  const company = user.companyName ?? "their company";

  function submit() {
    start(async () => {
      const result = await grantApplication(user.id, appId, { role: role.trim() || null, isAppAdmin });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(grant ? "Access changed" : "Access granted", { description: `${appName} · ${user.fullName}` });
      onDone();
    });
  }

  const Tag = grant ? "li" : "div";
  return (
    <Tag className="border-t border-rule bg-bench/40 px-5 py-4 first:border-t-0">
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="space-y-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {grant ? (
            <p className="text-sm font-semibold text-ink sm:col-span-2">{grant.name}</p>
          ) : (
            <Field label="Application" error={fields.applicationId}>
              {(p) => (
                <Select {...p} value={appId} onChange={(e) => setAppId(e.target.value)} autoFocus>
                  {user.canBeGiven.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <Field label={`Role in ${appName}`} optional error={fields.role} hint="Their role in the application, e.g. Pharmacist or Sales rep.">
            {(p) => <Input {...p} value={role} onChange={(e) => setRole(e.target.value)} maxLength={60} autoFocus={Boolean(grant)} />}
          </Field>
        </div>
        <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink">
          <input suppressHydrationWarning type="checkbox" className="mt-0.5 size-4 accent-hema" checked={isAppAdmin} onChange={(e) => setAppAdmin(e.target.checked)} />
          <span>
            Application admin
            <span className="block text-meta text-ink-3">
              Runs {appName} for {company}.
            </span>
          </span>
        </label>
        <FormError message={error} />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" size="sm" variant="primary" loading={pending} disabled={!appId}>
            {grant ? "Save" : "Grant access"}
          </Button>
          <Button size="sm" variant="quiet" onClick={onDone} disabled={pending}>
            Cancel
          </Button>
        </div>
      </form>
    </Tag>
  );
}
