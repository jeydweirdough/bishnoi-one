"use client";

import { Avatar, AvatarFallback } from "@/src/components/ui/avatar";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Checkbox } from "@/src/platform/ui/compat";
import { Pager } from "@/src/platform/ui/pager";
import { PAGE_SIZE, slicePage } from "@/src/platform/ui/paging";
import { SelectAllBox, SelectBox, SelectableRow, SelectionProvider } from "@/src/platform/bulk/selection";
import { Download, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Banner } from "@/src/platform/ui/alert";
import { LinkButton } from "@/src/platform/ui/ant-button";
import { AsyncButton, AsyncChip } from "@/src/platform/ui/async-button";
import { SearchInput } from "@/src/platform/ui/field";
import { Select } from "@/src/platform/ui/pickers";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { importRoles, setPersonAppRole, setPersonModule } from "./actions";
import { moduleLabel } from "./labels";
import { AddPerson, PersonMenu } from "./person-dialogs";
import { ImportPeople } from "./import-people";
import { EmployeesBulk } from "./people-bulk";
import type { AccessData, AccessPerson } from "./types";

const NONE = "";
/** Rows a page with an employee's panel open beside the list. */
const BESIDE_PANEL = 10;

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
  // A page at a time (2026-11-01). Until a page is picked, the one holding the open employee.
  const [picked, setPicked] = useState<number | null>(null);
  const at = shown.findIndex((p) => p.id === selected);
  // With an employee open, ten a page whatever the tab (2026-11-02): the same pages every time, and the panel
  // stands as tall as the list beside it.
  const size = panel ? BESIDE_PANEL : PAGE_SIZE;
  // Opening or closing an employee shows the page they're on, at that page's size.
  useEffect(() => setPicked(null), [selected, size]);
  const { rows: onPage, page } = slicePage(shown, picked ?? (at >= 0 ? Math.floor(at / size) + 1 : 1), size);

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

      {/* Yourself can't be switched off or deleted, so you aren't ticked; nor with an employee open beside the list. */}
      <SelectionProvider items={panel ? [] : onPage.filter((p) => p.id !== data.meId).map((p) => ({ id: p.id, name: p.fullName }))}>
      {/* Studio Admin's Users (2026-11-19): a card, its header with the title, what it is and the actions. */}
      <Card>
        <CardHeader className="border-b has-data-[slot=card-action]:grid-cols-1 md:has-data-[slot=card-action]:grid-cols-[1fr_auto]">
          <CardTitle className="text-xl leading-none">Employees</CardTitle>
          <CardDescription className="max-w-sm leading-snug">Your company&apos;s employees, the apps they open and their roles.</CardDescription>
          <CardAction className="col-start-1 row-start-auto flex w-full flex-wrap justify-start gap-2 justify-self-stretch md:col-start-2 md:row-span-2 md:row-start-1 md:w-auto md:justify-end md:justify-self-end">
            <div className="w-full md:w-64">
              <SearchInput placeholder="Search employees…" allowClear value={query} onChange={(e) => (setQuery(e.target.value), setPicked(1))} />
            </div>
            <Button asChild variant="outline" size="sm">
              <Link href="/platform/roles/people/bin">
                <Trash2 aria-hidden />
                Recycle bin
                {data.inBin > 0 && <Badge variant="secondary">{data.inBin}</Badge>}
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <a href="/platform/roles/people/export" download>
                <Download aria-hidden />
                Export
              </a>
            </Button>
            <ImportPeople />
            <AddPerson data={data} />
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 px-0">
        {toChoose.size > 0 && (
          <div className="flex flex-wrap items-center gap-3 px-4">
            <Checkbox checked={onlyToChoose} onChange={(e) => (setOnlyToChoose(e.target.checked), setPicked(1))}>
              Only those still to choose ({toChoose.size})
            </Checkbox>
          </div>
        )}

        {shown.length === 0 ? (
          <Empty icon="people" title="Nobody matches">
            Try another name or email.
          </Empty>
        ) : (
          <div className={panel ? "grid gap-4 px-4 lg:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)] lg:items-stretch" : ""}>
            <div className="flex flex-col overflow-x-auto">
              <table className={`w-full text-sm ${panel ? "" : "min-w-[48rem]"}`}>
                <thead>
                  <tr className="border-t border-b text-left text-sm text-muted-foreground">
                    {!panel && (
                      <th scope="col" className="w-12 py-3 pl-4">
                        <SelectAllBox />
                      </th>
                    )}
                    <th scope="col" className="py-3 pr-4 font-normal">Employee</th>
                    {!panel && (
                      <>
                        <th scope="col" className="py-3 pr-4 font-normal">Date added</th>
                        <th scope="col" className="py-3 pr-4 font-normal">Added by</th>
                        <th scope="col" className="py-3 pr-4 font-normal">Status</th>
                        <th scope="col" className="w-12 py-3 pr-4 text-right font-normal">Actions</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {onPage.map((p) => (
                    <PersonRow key={p.id} person={p} data={data} compact={Boolean(panel)} current={p.id === selected} />
                  ))}
                </tbody>
              </table>
              <div className="mt-auto px-4">
                <Pager total={shown.length} page={page} size={size} onPage={setPicked} noun={shown.length === 1 ? "employee" : "employees"} />
              </div>
            </div>
            {panel && <div className="flex flex-col [&>*]:flex-1">{panel}</div>}
          </div>
        )}
        </CardContent>
      </Card>
      {!panel && <EmployeesBulk data={data} />}
      </SelectionProvider>
    </div>
  );
}

const addedOn = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString("en-PH", { day: "numeric", month: "short", year: "numeric" }) : "—");

/** The avatar's colour, from the name (as Studio Admin's users list). */
const TONES = [
  "[&_[data-slot=avatar-fallback]]:bg-amber-100 [&_[data-slot=avatar-fallback]]:text-amber-700",
  "[&_[data-slot=avatar-fallback]]:bg-rose-100 [&_[data-slot=avatar-fallback]]:text-rose-700",
  "[&_[data-slot=avatar-fallback]]:bg-violet-100 [&_[data-slot=avatar-fallback]]:text-violet-700",
  "[&_[data-slot=avatar-fallback]]:bg-sky-100 [&_[data-slot=avatar-fallback]]:text-sky-700",
  "[&_[data-slot=avatar-fallback]]:bg-emerald-100 [&_[data-slot=avatar-fallback]]:text-emerald-700",
  "[&_[data-slot=avatar-fallback]]:bg-indigo-100 [&_[data-slot=avatar-fallback]]:text-indigo-700",
  "[&_[data-slot=avatar-fallback]]:bg-orange-100 [&_[data-slot=avatar-fallback]]:text-orange-700",
];
const toneOf = (name: string) => TONES[name.length % TONES.length];

/** Active or switched off, as Studio Admin's status badge: a dot and the word. */
function StatusBadge({ active }: { active: boolean }) {
  return (
    <Badge variant="outline" className={`gap-1.5 border px-2 py-1 font-medium ${active ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-600" : "border-border bg-muted/50 text-muted-foreground"}`}>
      <span className={`size-1.5 rounded-full ${active ? "bg-emerald-500" : "bg-muted-foreground"}`} />
      {active ? "Active" : "Switched off"}
    </Badge>
  );
}

/** A person in the table: their name opens them in the panel beside it (Zoho Directory's Users). */
function PersonRow({ person, data, compact, current }: { person: AccessPerson; data: AccessData; compact: boolean; current: boolean }) {
  const initials = person.fullName.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
  const name = (
    <Link href={`/platform/roles/people?person=${person.id}`} className="flex min-w-0 items-center gap-3" aria-current={current ? "page" : undefined}>
      <Avatar size="lg" className={`font-medium ${toneOf(person.fullName)}`}>
        <AvatarFallback>{initials}</AvatarFallback>
      </Avatar>
      <span className="min-w-0">
        <span className="flex items-center gap-2 truncate text-sm font-medium text-foreground hover:underline">
          <span className="truncate">{person.fullName}</span>
          {person.isCompanyAdmin && <Badge variant="outline">Admin</Badge>}
        </span>
        <span className="block truncate text-sm text-muted-foreground">{person.email}</span>
      </span>
    </Link>
  );
  if (compact) {
    return (
      <tr className={current ? "bg-muted" : "hover:bg-muted/50"}>
        <td className="max-w-[22rem] px-2 py-2.5">{name}</td>
      </tr>
    );
  }
  return (
    <SelectableRow id={person.id} className="hover:bg-muted/50">
      <td className="w-12 py-4 pl-4">{person.id !== data.meId && <SelectBox id={person.id} label={person.fullName} />}</td>
      <td className="max-w-[22rem] py-4 pr-4">{name}</td>
      <td className="py-4 pr-4 whitespace-nowrap">{addedOn(person.addedAt)}</td>
      <td className="max-w-[12rem] truncate py-4 pr-4 text-muted-foreground">{person.addedBy ?? "—"}</td>
      <td className="py-4 pr-4">
        <StatusBadge active={person.status === "active"} />
      </td>
      <td className="py-4 pr-4 text-right">
        <PersonMenu person={person} isMe={person.id === data.meId} modules={data.modules.map((m) => m.key)} colleagues={data.people.filter((c) => c.status === "active").map((c) => ({ id: c.id, name: c.fullName }))} />
      </td>
    </SelectableRow>
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
