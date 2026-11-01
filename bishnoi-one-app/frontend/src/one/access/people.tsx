"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Banner } from "@/src/platform/ui/alert";
import { AsyncButton, AsyncChip } from "@/src/platform/ui/async-button";
import { SearchInput } from "@/src/platform/ui/field";
import { Select } from "@/src/platform/ui/pickers";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { importRoles, setPersonAppRole, setPersonModule } from "./actions";
import { moduleLabel } from "./labels";
import { AddPerson, PersonMenu } from "./person-dialogs";
import { ImportPeople } from "./import-people";
import type { AccessData, AccessPerson } from "./types";

const NONE = "";

/** Everyone at the company, as a table: their role in each app and the apps they may open, each changed where it's shown. */
export function PeopleList({ data, selected = null, panel = null }: { data: AccessData; selected?: string | null; panel?: ReactNode }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [onlyToChoose, setOnlyToChoose] = useState(false);
  const toChoose = new Set(data.toChoose);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return data.people.filter(
      (p) => (!onlyToChoose || toChoose.has(p.id)) && (!q || p.fullName.toLowerCase().includes(q) || p.email.toLowerCase().includes(q)),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.people, query, onlyToChoose, data.toChoose]);

  async function bringIn() {
    const r = await importRoles();
    if (!r.ok) {
      toast.error(r.error);
      return;
    }
    const { rolesMade, peopleGiven, toChoose: left, unreachable } = r.data;
    toast.success(`${rolesMade} ${rolesMade === 1 ? "role" : "roles"} brought in, ${peopleGiven} ${peopleGiven === 1 ? "employee" : "employees"} given theirs`, {
      description: [left ? `${left} to choose for: they have different roles in different modules.` : "", unreachable.length ? `Not reached: ${unreachable.join(", ")}.` : ""]
        .filter(Boolean)
        .join(" ") || undefined,
    });
    router.refresh();
  }

  return (
    <div className="space-y-4">
      {data.roles.length === 0 ? (
        <Banner
          tone="info"
          action={
            <AsyncButton size="sm" onRun={bringIn}>
              Bring in today&apos;s roles
            </AsyncButton>
          }
        >
          No roles here yet. Bring in the roles each module has today: the same names become one role, and each person gets theirs.
        </Banner>
      ) : toChoose.size > 0 ? (
        <Banner tone="warn">
          {toChoose.size} {toChoose.size === 1 ? "employee has" : "employees have"} no role here yet. Until you choose one, each module goes by the
          role it gave them.
        </Banner>
      ) : null}

      <Sheet className="px-5 pt-4 pb-2">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-full max-w-xs">
            <SearchInput placeholder="Find an employee" allowClear value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          {toChoose.size > 0 && (
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-ink-2">
              <input suppressHydrationWarning type="checkbox" checked={onlyToChoose} onChange={(e) => setOnlyToChoose(e.target.checked)} />
              Only those still to choose ({toChoose.size})
            </label>
          )}
          <span className="ml-auto text-meta text-ink-3">
            {shown.length} of {data.people.length}
          </span>
          <Link href="/platform/roles/people/bin" className="text-meta text-ink-2 hover:text-hema hover:underline">
            Recycle bin{data.inBin > 0 ? ` (${data.inBin})` : ""}
          </Link>
          <a href="/platform/roles/people/export" className="text-meta text-ink-2 hover:text-hema hover:underline" download>
            Export
          </a>
          <ImportPeople />
          <AddPerson data={data} />
        </div>

        {shown.length === 0 ? (
          <Empty icon="people" title="Nobody matches">
            Try another name or email.
          </Empty>
        ) : (
          <div className={panel ? "mt-3 grid gap-4 lg:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)] lg:items-start" : "mt-3"}>
            <div className="overflow-x-auto">
              <table className={`w-full text-sm ${panel ? "" : "min-w-[48rem]"}`}>
                <thead>
                  <tr className="border-b border-rule text-left text-meta text-ink-3">
                    <th scope="col" className="py-2 pr-4 font-medium">{panel ? "Name / email" : "Name"}</th>
                    {!panel && (
                      <>
                        <th scope="col" className="py-2 pr-4 font-medium">Email</th>
                        <th scope="col" className="py-2 pr-4 font-medium">Date added</th>
                        <th scope="col" className="py-2 pr-4 font-medium">Added by</th>
                        <th scope="col" className="py-2 pr-4 font-medium">Status</th>
                        <th scope="col" className="w-12 py-2 font-medium"><span className="sr-only">Actions</span></th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {shown.map((p) => (
                    <PersonRow key={p.id} person={p} data={data} compact={Boolean(panel)} current={p.id === selected} />
                  ))}
                </tbody>
              </table>
            </div>
            {panel}
          </div>
        )}
      </Sheet>
    </div>
  );
}

const addedOn = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString("en-PH", { day: "numeric", month: "short", year: "numeric" }) : "—");

/** A person in the table: their name opens them in the panel beside it (Zoho Directory's Users). */
function PersonRow({ person, data, compact, current }: { person: AccessPerson; data: AccessData; compact: boolean; current: boolean }) {
  const initials = person.fullName.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
  const name = (
    <Link href={`/platform/roles/people?person=${person.id}`} className="flex min-w-0 items-center gap-3" aria-current={current ? "page" : undefined}>
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-bench text-meta font-semibold text-ink-2" aria-hidden>
        {initials}
      </span>
      <span className="min-w-0">
        <span className="block truncate font-semibold text-ink hover:underline">
          {person.fullName}
          {person.isCompanyAdmin && <span className="ml-2 rounded border border-sage-deep px-1 text-[0.625rem] font-semibold tracking-wide text-sage-deep uppercase align-middle">Admin</span>}
        </span>
        {compact && <span className="block truncate text-meta text-ink-3">{person.email}</span>}
      </span>
    </Link>
  );
  if (compact) {
    return (
      <tr className={current ? "bg-hema-tint/60" : "hover:bg-bench/50"}>
        <td className="max-w-[22rem] px-2 py-2.5">{name}</td>
      </tr>
    );
  }
  return (
    <tr className="group hover:bg-bench/40">
      <td className="max-w-[16rem] py-2.5 pr-4">{name}</td>
      <td className="max-w-[16rem] truncate py-2.5 pr-4 text-ink-2">{person.email}</td>
      <td className="py-2.5 pr-4 whitespace-nowrap text-ink-2">{addedOn(person.addedAt)}</td>
      <td className="max-w-[12rem] truncate py-2.5 pr-4 text-ink-2">{person.addedBy ?? "—"}</td>
      <td className="py-2.5 pr-4">
        {person.status === "active" ? (
          <span className="rounded-full bg-[#e6f2e1] px-2 py-0.5 text-meta text-[#3f6f35]">Active</span>
        ) : (
          <span className="rounded-full bg-danger-tint px-2 py-0.5 text-meta text-danger">Switched off</span>
        )}
      </td>
      <td className="py-2.5 text-right">
        <PersonMenu person={person} isMe={person.id === data.meId} modules={data.modules.map((m) => m.key)} domain={data.company.emailDomain} />
      </td>
    </tr>
  );
}

/** Their role in each app they may open (2026-10-31): the role beside the app's chip, only roles with something in that app. */
export function AppRoles({ person, data }: { person: AccessPerson; data: AccessData }) {
  const router = useRouter();
  const [saving, start] = useTransition();
  const has = new Set(person.apps.map((a) => a.key));
  const opened = data.modules.filter((m) => has.has(m.key));
  const rolesFor = (key: string) => data.roles.filter((r) => r.isAdmin || (r.permissions[key]?.length ?? 0) > 0);

  function giveAppRole(key: string, roleId: string) {
    start(async () => {
      const r = await setPersonAppRole(person.id, key, roleId || null);
      if (!r.ok) toast.error(r.error);
      else router.refresh();
    });
  }

  if (person.isCompanyAdmin) return <p className="text-sm text-ink-2">Administrator in every app</p>;
  if (opened.length === 0) return <p className="text-meta text-ink-3">Give them an app to choose their role in it.</p>;
  return (
    <div className="space-y-1.5" aria-label={`${person.fullName}'s role in each app`}>
      {opened.map((m) => {
        const current = person.apps.find((a) => a.key === m.key)?.roleId ?? null;
        const choices = rolesFor(m.key);
        return (
          <div key={m.key} className="flex items-center gap-2">
            <Select
              aria-label={`${person.fullName}'s role in ${moduleLabel(m)}`}
              className="min-w-0 flex-1"
              value={current ?? NONE}
              onChange={(e) => giveAppRole(m.key, e.target.value)}
              disabled={saving || choices.length === 0}
            >
              <option value={NONE}>No role yet</option>
              {[...choices, ...data.roles.filter((r) => r.id === current && !choices.includes(r))].map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </Select>
            <span className="shrink-0 rounded-md border border-hema bg-hema-tint px-2.5 py-0.5 text-meta font-semibold text-ink">{moduleLabel(m)}</span>
          </div>
        );
      })}
    </div>
  );
}

/** The apps they may open: each chip gives or takes one away. */
export function AppChips({ person, data }: { person: AccessPerson; data: AccessData }) {
  const router = useRouter();
  const has = new Set(person.apps.map((a) => a.key));

  async function toggle(key: string, on: boolean) {
    const r = await setPersonModule(person.id, key, on);
    if (!r.ok) toast.error(r.error);
    else router.refresh();
  }

  return (
    <div className="flex flex-wrap gap-1.5" aria-label={`Apps ${person.fullName} may open`}>
      {data.modules.map((m) => {
        const on = has.has(m.key);
        return (
          <AsyncChip
            key={m.key}
            onRun={() => toggle(m.key, !on)}
            aria-pressed={on}
            title={on ? `Take ${moduleLabel(m)} away` : `Give ${moduleLabel(m)}`}
            className={`rounded-md border px-3 py-1 text-meta transition-colors ${
              on ? "border-hema bg-hema-tint font-semibold text-ink" : "border-rule-strong bg-sheet text-ink-3 hover:border-hema"
            }`}
          >
            {moduleLabel(m)}
          </AsyncChip>
        );
      })}
    </div>
  );
}
