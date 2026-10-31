"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
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
export function PeopleList({ data }: { data: AccessData }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [onlyToChoose, setOnlyToChoose] = useState(false);
  const toChoose = new Set(data.toChoose);
  const names = Object.fromEntries(data.modules.map((m) => [m.key, moduleLabel(m)]));

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
    toast.success(`${rolesMade} ${rolesMade === 1 ? "role" : "roles"} brought in, ${peopleGiven} ${peopleGiven === 1 ? "person" : "people"} given theirs`, {
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
          {toChoose.size} {toChoose.size === 1 ? "person has" : "people have"} no role here yet. Until you choose one, each module goes by the
          role it gave them.
        </Banner>
      ) : null}

      <Sheet className="px-5 pt-4 pb-2">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-full max-w-xs">
            <SearchInput placeholder="Find a person" allowClear value={query} onChange={(e) => setQuery(e.target.value)} />
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
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[56rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-meta font-medium text-ink-3">
                  <th scope="col" className="py-2 pr-4 font-medium">Person</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Role in each app</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Apps</th>
                  <th scope="col" className="w-12 py-2 font-medium"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {shown.map((p) => (
                  <PersonRow key={p.id} person={p} data={data} names={names} toChoose={toChoose.has(p.id)} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </div>
  );
}

function PersonRow({ person, data, names, toChoose }: { person: AccessPerson; data: AccessData; names: Record<string, string>; toChoose: boolean }) {
  const today = person.apps.filter((a) => a.role);
  return (
    <tr className="group align-top">
      <td className="max-w-[16rem] py-3 pr-4">
        <Link href={`/platform/roles/people/${person.id}`} className="block truncate font-semibold text-ink hover:underline">
          {person.fullName}
        </Link>
        <span className="block truncate text-meta text-ink-3">
          {person.email}
          {person.title ? ` · ${person.title}` : ""}
        </span>
        {(person.isCompanyAdmin || person.status !== "active") && (
          <span className="mt-1 flex flex-wrap gap-1">
            {person.isCompanyAdmin && <span className="rounded-full bg-bench px-2 py-0.5 text-meta text-ink-3">Company administrator</span>}
            {person.status !== "active" && <span className="rounded-full bg-bench px-2 py-0.5 text-meta text-ink-3">Switched off</span>}
          </span>
        )}
      </td>
      <td className="min-w-[16rem] py-3 pr-4">
        <AppRoles person={person} data={data} />
        {toChoose && today.length > 0 && (
          <p className="mt-1 text-meta text-promo-ink">Today: {today.map((a) => `${names[a.key] ?? a.key} ${a.role}`).join(" · ")}</p>
        )}
      </td>
      <td className="py-3 pr-4">
        <AppChips person={person} data={data} />
      </td>
      <td className="py-3 text-right">
        <PersonMenu person={person} isMe={person.id === data.meId} modules={data.modules.map((m) => m.key)} />
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
