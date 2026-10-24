"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/console/platform/ui/button";
import { ConfirmButton } from "@/src/modules/console/platform/ui/confirm";
import { FormError } from "@/src/modules/console/platform/ui/field";
import { HealthMark } from "@/src/modules/console/components/marks";
import { setCompanyApplications } from "@/src/modules/console/actions/organizations";
import { plural } from "@/src/modules/console/lib/words";
import type { CompanyDetail, Options } from "@/src/modules/console/lib/types";

/**
 * Which applications a company may use. Every registered application is a
 * tick; the ones it has show how they're doing and how many of its people use
 * them. Withdrawing one takes it from those people too, so that asks first.
 */
export function CompanyApps({
  company,
  applications,
  canChange,
}: {
  company: Pick<CompanyDetail, "id" | "name" | "applications">;
  applications: Options["applications"];
  canChange: boolean;
}) {
  const had = company.applications.map((a) => a.id);
  const [chosen, setChosen] = useState<string[]>(had);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const have = new Map(company.applications.map((a) => [a.id, a]));
  // An application it has that is no longer registered as active still shows, so it can be withdrawn.
  const all = [...applications, ...company.applications.filter((a) => !applications.some((o) => o.id === a.id))];
  const removing = had.filter((id) => !chosen.includes(id));
  const adding = chosen.filter((id) => !had.includes(id));
  const losing = removing.reduce((n, id) => n + (have.get(id)?.userCount ?? 0), 0);
  const changed = removing.length + adding.length > 0;

  async function save(): Promise<boolean> {
    const result = await setCompanyApplications(company.id, chosen);
    if (!result.ok) {
      setError(result.error);
      return false;
    }
    setError(null);
    const { withdrawnFromPeople: n } = result.data;
    toast.success("Applications saved", { description: n ? `Access removed for ${plural(n, "user")} at ${company.name}.` : company.name });
    return true;
  }

  if (all.length === 0) {
    return <p className="px-5 py-6 text-meta text-ink-3">No applications are registered yet. Register one under Applications first.</p>;
  }

  return (
    <div>
      <ul className="divide-y divide-rule" role="list">
        {all.map((a) => {
          const detail = have.get(a.id);
          const on = chosen.includes(a.id);
          return (
            <li key={a.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3">
              <label className={`inline-flex min-w-0 flex-1 items-center gap-2.5 text-sm ${canChange ? "cursor-pointer" : ""}`}>
                <input suppressHydrationWarning
                  type="checkbox"
                  className="size-4 accent-hema disabled:cursor-default"
                  checked={on}
                  disabled={!canChange}
                  aria-label={`${company.name} has ${a.name}`}
                  onChange={(e) => setChosen(e.target.checked ? [...chosen, a.id] : chosen.filter((id) => id !== a.id))}
                />
                <span className={`font-semibold ${on ? "text-ink" : "text-ink-3"}`}>{a.name}</span>
              </label>
              {detail ? (
                <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <HealthMark status={detail.status} />
                  <Link href={`/platform/accounts?company=${company.id}&application=${a.id}`} className="text-meta text-ink-2 hover:text-hema hover:underline">
                    {plural(detail.userCount, "user")}
                  </Link>
                </span>
              ) : (
                <span className="text-meta text-ink-3">{on ? "Assigned on save" : "Not assigned"}</span>
              )}
              {detail && !on && detail.userCount > 0 && (
                <span className="w-full text-meta text-danger">Withdrawing it also takes it from its {plural(detail.userCount, "user")} here.</span>
              )}
            </li>
          );
        })}
      </ul>
      {canChange && (
        <div className="space-y-3 border-t border-rule px-5 py-4">
          <p className="text-meta text-ink-3">
            Withdrawing an application also withdraws it from every person at {company.name}. Giving it back doesn&apos;t give it back to them.
          </p>
          <FormError message={error} />
          <div className="flex flex-wrap gap-2">
            {removing.length > 0 ? (
              <ConfirmButton
                label="Save applications"
                triggerVariant="primary"
                title={`Remove ${plural(removing.length, "application")} from ${company.name}?`}
                body={
                  <>
                    {removing.map((id) => have.get(id)?.name).join(", ")} will be removed from {company.name}
                    {losing > 0 ? <> and from the {plural(losing, "user")} there who use {removing.length === 1 ? "it" : "them"}</> : null}. Their roles in{" "}
                    {removing.length === 1 ? "it" : "them"} are deleted.
                  </>
                }
                confirmLabel="Remove and save"
                onConfirm={save}
              />
            ) : (
              <Button variant="primary" disabled={!changed} loading={pending} onClick={() => start(async () => void (await save()))}>
                Save applications
              </Button>
            )}
            {changed && (
              <Button variant="quiet" onClick={() => setChosen(had)} disabled={pending}>
                Undo changes
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
