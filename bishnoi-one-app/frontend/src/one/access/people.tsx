"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Banner } from "@/src/platform/ui/alert";
import { AsyncButton, AsyncChip } from "@/src/platform/ui/async-button";
import { SearchInput } from "@/src/platform/ui/field";
import { Select } from "@/src/platform/ui/pickers";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { givePersonRole, importRoles, setPersonModule } from "./actions";
import { moduleLabel } from "./labels";
import type { AccessData, AccessPerson } from "./types";

const NONE = "";

/** Everyone at the company: their one role, and the modules they may open, each changed where it's shown. */
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
              <input type="checkbox" checked={onlyToChoose} onChange={(e) => setOnlyToChoose(e.target.checked)} />
              Only those still to choose ({toChoose.size})
            </label>
          )}
          <span className="ml-auto text-meta text-ink-3">
            {shown.length} of {data.people.length}
          </span>
        </div>

        {shown.length === 0 ? (
          <Empty icon="people" title="Nobody matches">
            Try another name or email.
          </Empty>
        ) : (
          <ul className="mt-3 divide-y divide-rule">
            {shown.map((p) => (
              <PersonRow key={p.id} person={p} data={data} names={names} toChoose={toChoose.has(p.id)} />
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}

function PersonRow({ person, data, names, toChoose }: { person: AccessPerson; data: AccessData; names: Record<string, string>; toChoose: boolean }) {
  const router = useRouter();
  const [saving, start] = useTransition();
  const has = new Set(person.apps.map((a) => a.key));
  const today = person.apps.filter((a) => a.role);

  function giveRole(roleId: string) {
    start(async () => {
      const r = await givePersonRole(person.id, roleId || null);
      if (!r.ok) toast.error(r.error);
      else router.refresh();
    });
  }

  async function toggle(key: string, on: boolean) {
    const r = await setPersonModule(person.id, key, on);
    if (!r.ok) toast.error(r.error);
    else router.refresh();
  }

  return (
    <li className="grid gap-3 py-3 lg:grid-cols-[minmax(0,1.2fr)_15rem_minmax(0,1.6fr)] lg:items-center">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-ink">
          {person.fullName}
          {person.isCompanyAdmin && <span className="ml-2 rounded-full bg-bench px-2 py-0.5 text-meta font-normal text-ink-3">Company administrator</span>}
          {person.status !== "active" && <span className="ml-2 rounded-full bg-bench px-2 py-0.5 text-meta font-normal text-ink-3">Suspended</span>}
        </p>
        <p className="truncate text-meta text-ink-3">
          {person.email}
          {person.title ? ` · ${person.title}` : ""}
        </p>
      </div>

      <div className="min-w-0">
        <Select aria-label={`${person.fullName}'s role`} value={person.roleId ?? NONE} onChange={(e) => giveRole(e.target.value)} disabled={saving || data.roles.length === 0}>
          <option value={NONE}>No role yet</option>
          {data.roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
        {toChoose && today.length > 0 && (
          <p className="mt-1 text-meta text-promo-ink">Today: {today.map((a) => `${names[a.key] ?? a.key} ${a.role}`).join(" · ")}</p>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5" aria-label={`Modules ${person.fullName} may open`}>
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
    </li>
  );
}
