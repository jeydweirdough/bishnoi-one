"use client";

import { Check, ChevronRight, Pencil, Plus, X } from "lucide-react";
import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { DEPARTMENT_ICONS, Icon, knownIcon, moduleIcon, type IconName } from "@/src/platform/ui/icons";
import { Sheet } from "@/src/platform/ui/sheet";
import { addDepartment, addDivision, addHeadquarters, addTeam, updateDepartment, updateHeadquarters, updateTeam } from "../actions/admin";
import type { OrgDivision, OrgTeam } from "@/src/platform/lib/types";
import s from "./teams-tree.module.css";

// The company as a tree: the company, its departments, their divisions and
// teams, and the teams' headquarters. Sales is the department that holds the
// six sales divisions; every other department holds its teams directly.
// Things are added where their branch ends, and a team or headquarters is
// renamed or switched off right where it sits. Headquarters stay folded into a
// count until asked for, and the departments outside Sales start folded.

type Outcome = { ok: true } | { ok: false; error: string };
// A department: Sales (which holds divisions) or one that is its own division.
type Department = { key: string; name: string; divisions: OrgDivision[]; own: OrgDivision | null };

const SALES = "sales";
const ADD_DEPARTMENT = "department:new";
const ADD_DIVISION = "division:new";

/** A department an admin added wears the icon they picked; a built-in one wears its module's. */
function departmentIcon(d: OrgDivision): IconName {
  return knownIcon(d.icon) ?? moduleIcon(d.code);
}

const teamKey = (d: string, t: string) => `${d}/${t}`;
const hqKey = (d: string, t: string, h: string) => `${d}/${t}/${h}`;

/** A node's frame. Switched-off things are dashed and faint; the selected one carries the hema ring. */
function frame(off: boolean, selected: boolean): string {
  const base = "flex h-10 items-center gap-2 rounded-[3px] border px-2.5 text-sm transition-colors";
  if (selected) return `${base} border-hema bg-sheet ring-2 ring-hema/15`;
  if (off) return `${base} border-dashed border-rule-strong bg-bench/50 text-ink-3`;
  return `${base} border-rule bg-sheet shadow-[0_1px_2px_rgb(20_22_30/0.06)] hover:border-control`;
}

function Off() {
  return (
    <span className="inline-flex h-5 shrink-0 items-center rounded-[2px] border border-rule-strong px-1 text-stamp text-ink-3 uppercase">
      Off
    </span>
  );
}

/**
 * The five levels of the tree, in order, so the branches can be read at a glance.
 * The last two carry a + because they are the ones this screen can add to.
 */
function Levels() {
  const levels: { name: string; add: boolean }[] = [
    { name: "Company", add: false },
    { name: "Departments", add: true },
    { name: "Sales divisions", add: true },
    { name: "Teams", add: true },
    { name: "Headquarters", add: true },
  ];
  return (
    <ol className="mb-3 flex flex-wrap items-center gap-1" aria-label="The levels of the tree">
      {levels.map((level, i) => (
        <li key={level.name} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="size-3.5 shrink-0 text-ink-3" aria-hidden />}
          <span
            className={`inline-flex h-7 items-center gap-1.5 rounded-[3px] border px-2 text-meta ${
              level.add ? "border-rule bg-sheet text-ink-2" : "border-dashed border-rule-strong text-ink-3"
            }`}
          >
            {level.name}
            {level.add && <Plus className="size-3 text-hema" aria-label="can be added here" />}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Typing a name into the tree: the new or renamed node itself becomes the field. */
function NameField({
  label,
  initial = "",
  placeholder,
  icon,
  saveLabel,
  onSave,
  onCancel,
}: {
  label: string;
  initial?: string;
  placeholder?: string;
  icon: IconName;
  saveLabel: string;
  onSave: (name: string) => Promise<Outcome>;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const name = value.trim();
  const unchanged = name === initial.trim();

  return (
    <form
      noValidate
      className="animate-reshape"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.length < 2 || unchanged) return;
        start(async () => {
          const result = await onSave(name);
          if (!result.ok) setError(result.error);
        });
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape" && !pending) {
          e.stopPropagation();
          onCancel();
        }
      }}
    >
      <div className="flex h-10 items-center gap-1.5 rounded-[3px] border border-hema bg-sheet pr-1 pl-2.5 ring-2 ring-hema/15">
        <Icon name={icon} className="size-4 text-ink-3" />
        <input
          aria-label={label}
          aria-invalid={error ? true : undefined}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          maxLength={80}
          placeholder={placeholder}
          autoFocus
          className="h-full min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3/80"
        />
        <button
          type="submit"
          aria-label={saveLabel}
          title={saveLabel}
          disabled={name.length < 2 || unchanged || pending}
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-[3px] bg-hema text-white hover:bg-hema-hover disabled:opacity-40"
        >
          <Check className="size-4" aria-hidden />
        </button>
        <button
          type="button"
          aria-label="Cancel"
          title="Cancel (Esc)"
          onClick={onCancel}
          disabled={pending}
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-[3px] text-ink-3 hover:bg-bench hover:text-ink"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
      {error && <p className="mt-1 text-meta text-danger">{error}</p>}
      {!error && name.length === 1 && <p className="mt-1 text-meta text-ink-3">Two letters or more.</p>}
    </form>
  );
}

/** Where a branch ends: add the next thing there. Quiet until pointed at, so a tree of them doesn't shout. */
function AddHere({ label, full, onClick }: { label: string; full: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={full}
      className="flex h-10 w-full items-center gap-2 rounded-[3px] border border-dashed border-rule-strong px-2.5 text-sm font-semibold text-ink-3 hover:border-hema hover:bg-hema-tint hover:text-hema focus-visible:border-hema focus-visible:text-hema"
    >
      <Plus className="size-4 shrink-0" aria-hidden />
      <span className="truncate">{label}</span>
    </button>
  );
}

function Twisty({ open }: { open: boolean }) {
  return <ChevronRight aria-hidden className={`size-3.5 shrink-0 text-ink-3 transition-transform ${open ? "rotate-90" : ""}`} />;
}

/** The icon a department wears in the tree and the sidebar. Picking one saves it at once. */
function IconChoice({ value, onPick }: { value: IconName; onPick: (icon: IconName) => void }) {
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label="Icon">
      {DEPARTMENT_ICONS.map(({ name, label }) => (
        <button
          key={name}
          type="button"
          aria-pressed={value === name}
          aria-label={label}
          title={label}
          onClick={() => onPick(name)}
          className={`inline-flex size-7 items-center justify-center rounded-[3px] border ${
            value === name ? "border-hema bg-hema-tint text-hema" : "border-rule text-ink-3 hover:border-control"
          }`}
        >
          <Icon name={name} className="size-4" />
        </button>
      ))}
    </div>
  );
}

export function TeamsEditor({ company, divisions }: { company: string; divisions: OrgDivision[] }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [newIcon, setNewIcon] = useState<IconName>("divisions");
  const [hqOpen, setHqOpen] = useState<Set<string>>(() => new Set());
  // Sales opens on its divisions; the other departments start folded to their team count.
  const [closed, setClosed] = useState<Set<string>>(
    () => new Set(divisions.filter((d) => d.kind !== "sales").map((d) => d.code)),
  );

  const departments: Department[] = [
    { key: SALES, name: "Sales", divisions: divisions.filter((d) => d.kind === "sales"), own: null },
    ...divisions.filter((d) => d.kind !== "sales").map((d) => ({ key: d.code, name: d.name, divisions: [], own: d })),
  ].filter((dep) => dep.own !== null || dep.divisions.length > 0);

  const flip = (set: Set<string>, key: string) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  };
  const toggle = (key: string) => setClosed((c) => flip(c, key));

  function select(key: string) {
    setSelected((current) => (current === key ? null : key));
    setRenaming(false);
    setAdding(null);
  }

  function startAdding(key: string) {
    setAdding(key);
    setSelected(null);
    setRenaming(false);
  }

  function toggleHeadquarters(division: string, team: OrgTeam) {
    const key = teamKey(division, team.code);
    const opening = !hqOpen.has(key);
    setHqOpen((open) => flip(open, key));
    // A team with none yet opens straight into naming the first one.
    if (opening && team.headquarters.length === 0) startAdding(`hq:${key}`);
  }

  const clear = () => {
    setSelected(null);
    setRenaming(false);
    setAdding(null);
  };

  /** What can be done to a department itself. A built-in one keeps its icon and stays. */
  function departmentActions(d: OrgDivision): ReactNode {
    return (
      <div className="mt-1 animate-reshape space-y-2">
        <div className="flex flex-wrap gap-1">
          <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setRenaming(true)}>
            Rename
          </Button>
          {!d.isBuiltIn &&
            (d.isActive ? (
              <ConfirmButton
                label="Switch off"
                triggerVariant="quiet"
                triggerSize="sm"
                title={`Switch off ${d.name}?`}
                body="It leaves the roles screen and nobody new can be assigned to it. Its teams, its people and their records stay exactly as they are."
                confirmLabel="Switch off"
                onConfirm={async () => {
                  const result = await updateDepartment(d.code, { isActive: false });
                  if (!result.ok) {
                    toast.error(result.error);
                    return false;
                  }
                  toast.success(`${d.name} switched off`);
                }}
              />
            ) : (
              <AsyncButton
                size="sm"
                variant="quiet"
                onRun={async () => {
                  const result = await updateDepartment(d.code, { isActive: true });
                  if (result.ok) toast.success(`${d.name} switched back on`);
                  else toast.error(result.error);
                }}
              >
                Switch back on
              </AsyncButton>
            ))}
        </div>
        {d.isBuiltIn ? (
          <p className="text-meta text-ink-3">Comes with Bishnoi One&apos;s modules: it keeps its icon and stays switched on.</p>
        ) : (
          <IconChoice
            value={departmentIcon(d)}
            onPick={async (icon) => {
              const result = await updateDepartment(d.code, { icon });
              if (!result.ok) toast.error(result.error);
            }}
          />
        )}
      </div>
    );
  }

  function teamActions(d: OrgDivision, team: OrgTeam): ReactNode {
    return (
      <div className="mt-1 flex animate-reshape flex-wrap gap-1">
        <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setRenaming(true)}>
          Rename
        </Button>
        {team.isActive ? (
          <ConfirmButton
            label="Switch off"
            triggerVariant="quiet"
            triggerSize="sm"
            title={`Switch off ${team.name} in ${d.name}?`}
            body="No new customers can be added to it. Its existing records stay, and people assigned to it still see them."
            confirmLabel="Switch off"
            onConfirm={async () => {
              const result = await updateTeam(d.code, team.code, { isActive: false });
              if (!result.ok) {
                toast.error(result.error);
                return false;
              }
              toast.success(`${team.name} switched off`);
            }}
          />
        ) : (
          <AsyncButton
            size="sm"
            variant="quiet"
            onRun={async () => {
              const result = await updateTeam(d.code, team.code, { isActive: true });
              if (result.ok) toast.success(`${team.name} switched back on`);
              else toast.error(result.error);
            }}
          >
            Switch back on
          </AsyncButton>
        )}
      </div>
    );
  }

  function headquartersBranch(d: OrgDivision, team: OrgTeam) {
    const key = teamKey(d.code, team.code);
    const addKey = `hq:${key}`;
    return (
      <ul className={s.children} aria-label={`${team.name} headquarters`}>
        {team.headquarters.map((hq) => {
          const nodeKey = `hq-node:${hqKey(d.code, team.code, hq.code)}`;
          const isSelected = selected === nodeKey;
          const isRenaming = isSelected && renaming;
          return (
            <li key={hq.code} className={s.item}>
              <div className={`${s.node} ${isRenaming ? s.wide : s.hq}`}>
                {isRenaming ? (
                  <NameField
                    label={`New name for ${hq.name}`}
                    initial={hq.name}
                    icon="headquarters"
                    saveLabel="Save name"
                    onCancel={() => setRenaming(false)}
                    onSave={async (name) => {
                      const result = await updateHeadquarters(d.code, team.code, hq.code, { name });
                      if (!result.ok) return result;
                      toast.success(`Renamed to ${name}`);
                      clear();
                      return { ok: true };
                    }}
                  />
                ) : (
                  <button
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => select(nodeKey)}
                    className={`${frame(!hq.isActive, isSelected)} w-full text-left`}
                  >
                    <Icon name="headquarters" className="size-4 text-ink-3" />
                    <span className={`line-clamp-2 min-w-0 flex-1 leading-tight ${hq.isActive ? "" : "line-through decoration-rule-strong"}`}>{hq.name}</span>
                    {!hq.isActive && <Off />}
                  </button>
                )}
                {isSelected && !renaming && (
                  // Headquarters are the last column, so their actions can run past the node.
                  <div className="mt-1 flex w-max animate-reshape gap-1">
                    <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setRenaming(true)}>
                      Rename
                    </Button>
                    <AsyncButton
                      size="sm"
                      variant="quiet"
                      onRun={async () => {
                        const result = await updateHeadquarters(d.code, team.code, hq.code, { isActive: !hq.isActive });
                        if (result.ok) toast.success(`${hq.name} switched ${hq.isActive ? "off" : "back on"}`);
                        else toast.error(result.error);
                      }}
                    >
                      {hq.isActive ? "Switch off" : "Switch back on"}
                    </AsyncButton>
                  </div>
                )}
              </div>
            </li>
          );
        })}
        <li className={s.item}>
          <div className={`${s.node} ${adding === addKey ? s.wide : s.hq}`}>
            {adding === addKey ? (
              <NameField
                label={`New headquarters for ${team.name} in ${d.name}`}
                placeholder="Headquarters name"
                icon="headquarters"
                saveLabel="Add headquarters"
                onCancel={() => setAdding(null)}
                onSave={async (name) => {
                  const result = await addHeadquarters(d.code, team.code, name);
                  if (!result.ok) return result;
                  toast.success(`${name} added to ${team.name}`);
                  setAdding(null);
                  return { ok: true };
                }}
              />
            ) : (
              <AddHere label="Add HQ" full={`Add a headquarters to ${team.name} in ${d.name}`} onClick={() => startAdding(addKey)} />
            )}
          </div>
        </li>
      </ul>
    );
  }

  function teamsBranch(d: OrgDivision) {
    const addKey = `team:${d.code}`;
    return (
      <ul className={s.children} aria-label={`${d.name} teams`}>
        {d.teams.map((team) => {
          const key = teamKey(d.code, team.code);
          const nodeKey = `team-node:${key}`;
          const isSelected = selected === nodeKey;
          const isRenaming = isSelected && renaming;
          const open = hqOpen.has(key);
          const count = team.headquarters.length;
          return (
            <li key={team.code} className={s.item}>
              <div className={`${s.node} ${isRenaming ? s.wide : s.team}`}>
                {isRenaming ? (
                  <NameField
                    label={`New name for ${team.name} in ${d.name}`}
                    initial={team.name}
                    icon="teams"
                    saveLabel="Save name"
                    onCancel={() => setRenaming(false)}
                    onSave={async (name) => {
                      const result = await updateTeam(d.code, team.code, { name });
                      if (!result.ok) return result;
                      toast.success(`Renamed to ${name}`);
                      clear();
                      return { ok: true };
                    }}
                  />
                ) : (
                  <div className={`${frame(!team.isActive, isSelected)} pr-1`}>
                    <button
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => select(nodeKey)}
                      className="flex min-w-0 flex-1 items-center gap-2 self-stretch text-left"
                    >
                      <Icon name="teams" className="size-4 text-ink-3" />
                      <span className="line-clamp-2 min-w-0 flex-1 leading-tight font-semibold">{team.name}</span>
                    </button>
                    {!team.isActive && <Off />}
                    <button
                      type="button"
                      aria-expanded={open}
                      aria-label={count ? `${count} headquarters in ${team.name}: ${open ? "fold" : "show"}` : `Add a headquarters to ${team.name}`}
                      title={count ? `${count} headquarters` : "Add a headquarters"}
                      onClick={() => toggleHeadquarters(d.code, team)}
                      className={`inline-flex h-7 shrink-0 items-center gap-1 rounded-[3px] px-1.5 text-meta tabular-nums hover:bg-bench ${
                        open ? "bg-bench text-ink" : "text-ink-3"
                      }`}
                    >
                      {count ? <Icon name="headquarters" className="size-3.5" /> : <Plus className="size-3.5" aria-hidden />}
                      {count || "HQ"}
                    </button>
                  </div>
                )}
                {isSelected && !renaming && teamActions(d, team)}
              </div>
              {open && headquartersBranch(d, team)}
            </li>
          );
        })}
        <li className={s.item}>
          <div className={`${s.node} ${adding === addKey ? s.wide : s.team}`}>
            {adding === addKey ? (
              <NameField
                label={`New team in ${d.name}`}
                placeholder="Team name"
                icon="teams"
                saveLabel="Add team"
                onCancel={() => setAdding(null)}
                onSave={async (name) => {
                  const result = await addTeam(d.code, name);
                  if (!result.ok) return result;
                  toast.success(`${name} added to ${d.name}`);
                  setAdding(null);
                  return { ok: true };
                }}
              />
            ) : (
              <AddHere label="Add team" full={`Add a team to ${d.name}`} onClick={() => startAdding(addKey)} />
            )}
          </div>
        </li>
      </ul>
    );
  }

  /** A division of Sales, opening on its teams. */
  function divisionNode(d: OrgDivision) {
    const open = !closed.has(d.code);
    return (
      <li key={d.code} className={s.item}>
        <div className={`${s.node} ${s.division}`}>
          <button
            type="button"
            aria-expanded={open}
            aria-label={`${d.name} division, ${d.teams.length} ${d.teams.length === 1 ? "team" : "teams"}`}
            onClick={() => toggle(d.code)}
            className={`${frame(false, false)} w-full text-left`}
          >
            <span className="line-clamp-2 min-w-0 flex-1 leading-tight font-semibold">{d.name}</span>
            {!open && <span className="text-meta text-ink-3 tabular-nums">{d.teams.length}</span>}
            <Twisty open={open} />
          </button>
        </div>
        {open && teamsBranch(d)}
      </li>
    );
  }

  return (
    <Sheet className="px-4 pt-4 pb-5 sm:px-6">
      <Levels />
      <p className="mb-4 max-w-[65ch] text-meta text-ink-3">
        The boxes under {company} are its departments. Sales holds the sales divisions; every other department holds its teams
        directly. Pick a department, team or headquarters to rename it or switch it off, and{" "}
        <Plus className="inline size-3.5 align-[-2px]" aria-label="Add" /> where a branch ends adds one there. A department you add
        holds teams and people; a sales division you add gets the sales screens too, and needs its price types choosing in Settings
        &rarr; Pricing. The ones that came with Bishnoi One can be renamed but not switched off.
      </p>
      <div
        className={s.tree}
        onKeyDown={(e) => {
          if (e.key === "Escape") clear();
        }}
      >
        <ul className={s.list} aria-label={`${company}: departments, divisions, teams and headquarters`}>
          <li className={s.item}>
            <div className={`${s.node} ${s.root}`}>
              <div className="flex h-10 items-center gap-2 rounded-[3px] bg-ink px-3 text-sm font-semibold text-white">
                <Icon name="company" className="size-4 text-white/75" />
                <span className="truncate">{company}</span>
              </div>
            </div>
            <ul className={s.children} aria-label="Departments">
              {departments.map((dep) => {
                const open = !closed.has(dep.key);
                const count = dep.own ? dep.own.teams.length : dep.divisions.length;
                const what = dep.own ? (count === 1 ? "team" : "teams") : "divisions";
                const nodeKey = `dep-node:${dep.key}`;
                const isSelected = selected === nodeKey;
                const isRenaming = isSelected && renaming;
                const off = dep.own ? !dep.own.isActive : false;
                return (
                  <li key={dep.key} className={s.item}>
                    <div className={`${s.node} ${isRenaming ? s.wide : s.department}`}>
                      {isRenaming && dep.own ? (
                        <NameField
                          label={`New name for ${dep.name}`}
                          initial={dep.name}
                          icon={departmentIcon(dep.own)}
                          saveLabel="Save name"
                          onCancel={() => setRenaming(false)}
                          onSave={async (name) => {
                            const result = await updateDepartment(dep.own!.code, { name });
                            if (!result.ok) return result;
                            toast.success(`Renamed to ${name}`);
                            clear();
                            return { ok: true };
                          }}
                        />
                      ) : (
                        <div className={`${frame(off, isSelected)} pr-1`}>
                          <button
                            type="button"
                            aria-expanded={open}
                            aria-label={`${dep.name} department, ${count} ${what}`}
                            onClick={() => toggle(dep.key)}
                            className="flex min-w-0 flex-1 items-center gap-2 self-stretch text-left"
                          >
                            <Icon name={dep.own ? departmentIcon(dep.own) : "divisions"} className="size-4 text-ink-3" />
                            <span
                              className={`line-clamp-2 min-w-0 flex-1 leading-tight font-semibold ${off ? "line-through decoration-rule-strong" : ""}`}
                            >
                              {dep.name}
                            </span>
                            {!open && <span className="text-meta text-ink-3 tabular-nums">{count}</span>}
                            <Twisty open={open} />
                          </button>
                          {off && <Off />}
                          {dep.own && (
                            <button
                              type="button"
                              aria-pressed={isSelected}
                              aria-label={`Change ${dep.name}`}
                              title="Rename, change its icon, switch it off"
                              onClick={() => select(nodeKey)}
                              className={`inline-flex size-7 shrink-0 items-center justify-center rounded-[3px] hover:bg-bench ${
                                isSelected ? "bg-bench text-ink" : "text-ink-3"
                              }`}
                            >
                              <Pencil className="size-3.5" aria-hidden />
                            </button>
                          )}
                        </div>
                      )}
                      {isSelected && !renaming && dep.own && departmentActions(dep.own)}
                    </div>
                    {open &&
                      (dep.own ? (
                        teamsBranch(dep.own)
                      ) : (
                        <ul className={s.children} aria-label={`${dep.name} divisions`}>
                          {dep.divisions.map(divisionNode)}
                          <li className={s.item}>
                            <div className={`${s.node} ${adding === ADD_DIVISION ? s.wide : s.division}`}>
                              {adding === ADD_DIVISION ? (
                                <NameField
                                  label={`New sales division in ${company}`}
                                  placeholder="Division name"
                                  icon="salesDivision"
                                  saveLabel="Add division"
                                  onCancel={() => setAdding(null)}
                                  onSave={async (name) => {
                                    const result = await addDivision(name);
                                    if (!result.ok) return result;
                                    toast.success(`${name} added. Choose its price types in Settings → Pricing.`);
                                    setAdding(null);
                                    return { ok: true };
                                  }}
                                />
                              ) : (
                                <AddHere
                                  label="Add division"
                                  full={`Add a sales division to ${company}`}
                                  onClick={() => startAdding(ADD_DIVISION)}
                                />
                              )}
                            </div>
                          </li>
                        </ul>
                      ))}
                  </li>
                );
              })}
              <li className={s.item}>
                <div className={`${s.node} ${adding === ADD_DEPARTMENT ? s.wide : s.department}`}>
                  {adding === ADD_DEPARTMENT ? (
                    <div className="space-y-2">
                      <NameField
                        label={`New department in ${company}`}
                        placeholder="Department name"
                        icon={newIcon}
                        saveLabel="Add department"
                        onCancel={() => setAdding(null)}
                        onSave={async (name) => {
                          const result = await addDepartment(name, newIcon);
                          if (!result.ok) return result;
                          toast.success(`${name} added, with a General team to put people in`);
                          setAdding(null);
                          return { ok: true };
                        }}
                      />
                      <IconChoice value={newIcon} onPick={setNewIcon} />
                    </div>
                  ) : (
                    <AddHere
                      label="Add department"
                      full={`Add a department to ${company}`}
                      onClick={() => startAdding(ADD_DEPARTMENT)}
                    />
                  )}
                </div>
              </li>
            </ul>
          </li>
        </ul>
      </div>
    </Sheet>
  );
}
