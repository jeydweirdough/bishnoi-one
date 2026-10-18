"use client";

import { useState } from "react";
import { Field, Select } from "@/src/platform/ui/field";
import type { AssignmentInput } from "../actions/admin";
import type { AppModule, OrgDivision, Role } from "@/src/platform/lib/types";

const ALL = "*";
const SETTINGS = "settings";

type Props = {
  roles: Role[];
  divisions: OrgDivision[];
  // Modules whose screens are another app's (Orders): not divisions, and only reach some.
  apps?: AppModule[];
  personName?: string;
  errors?: Record<string, string>;
  onChange: (value: AssignmentInput) => void;
};

/**
 * Role + module + scope, in that order, with a sentence underneath saying what
 * it means. Sales modules only cover their own division, so for those the
 * division is fixed and only the team is picked. Orders offers only the
 * divisions orders are raised in.
 */
export function AssignmentPicker({ roles, divisions, apps = [], personName = "They", errors = {}, onChange }: Props) {
  const [roleKey, setRoleKey] = useState(roles[0]?.key ?? "");
  const [moduleKey, setModuleKey] = useState(divisions[0]?.code ?? ALL);
  const [divisionCode, setDivisionCode] = useState<string>("");
  const [team, setTeam] = useState<string>("");

  const picked = divisions.find((d) => d.code === moduleKey);
  const app = apps.find((a) => a.key === moduleKey);
  // The divisions this module's grants can reach.
  const reachable = app?.reaches ? divisions.filter((d) => app.reaches?.includes(d.code)) : divisions;
  const ownDivisionOnly = picked ? !picked.spansDivisions : false;
  const effectiveDivision = ownDivisionOnly ? moduleKey : divisionCode;
  const division = divisions.find((d) => d.code === effectiveDivision);

  function emit(next: { roleKey?: string; moduleKey?: string; divisionCode?: string; team?: string }) {
    const r = next.roleKey ?? roleKey;
    const m = next.moduleKey ?? moduleKey;
    const own = divisions.find((d) => d.code === m && !d.spansDivisions);
    const d = m === SETTINGS ? "" : own ? m : (next.divisionCode ?? divisionCode);
    const t = m === SETTINGS || !d ? "" : (next.team ?? team);
    onChange({ roleKey: r, moduleKey: m, divisionCode: d || null, subdivisionCode: t || null });
  }

  const role = roles.find((r) => r.key === roleKey);
  const teamName = division?.teams.find((t) => t.code === team)?.name;
  const scope = ownDivisionOnly
    ? teamName
      ? `for the ${teamName} team only`
      : "for every team"
    : division
      ? teamName
        ? `for ${division.name}'s ${teamName} team only`
        : `for all of ${division.name}`
      : "across all divisions";
  const sentence =
    moduleKey === SETTINGS
      ? `on the Settings screens`
      : `in ${moduleKey === ALL ? "every module" : (app?.name ?? picked?.name)}, ${app && !division ? "in every division orders are raised in" : scope}`;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Role" error={errors.roleKey}>
          {(p) => (
            <Select
              {...p}
              value={roleKey}
              onChange={(e) => {
                setRoleKey(e.target.value);
                emit({ roleKey: e.target.value });
              }}
            >
              {roles.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Module" error={errors.moduleKey}>
          {(p) => (
            <Select
              {...p}
              value={moduleKey}
              onChange={(e) => {
                setModuleKey(e.target.value);
                setDivisionCode("");
                setTeam("");
                emit({ moduleKey: e.target.value, divisionCode: "", team: "" });
              }}
            >
              <option value={ALL}>All modules</option>
              {divisions.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name}
                </option>
              ))}
              {apps.map((a) => (
                <option key={a.key} value={a.key}>
                  {a.name} (its own app)
                </option>
              ))}
              <option value={SETTINGS}>Settings (admin screens)</option>
            </Select>
          )}
        </Field>
        {moduleKey !== SETTINGS && (
          <Field label="Division" error={errors.divisionCode} hint={ownDivisionOnly ? `${picked?.name} only has its own records.` : undefined}>
            {(p) =>
              ownDivisionOnly ? (
                <Select {...p} value={moduleKey} disabled>
                  <option value={moduleKey}>{picked?.name}</option>
                </Select>
              ) : (
                <Select
                  {...p}
                  value={divisionCode}
                  onChange={(e) => {
                    setDivisionCode(e.target.value);
                    setTeam("");
                    emit({ divisionCode: e.target.value, team: "" });
                  }}
                >
                  <option value="">All divisions</option>
                  {reachable.map((d) => (
                    <option key={d.code} value={d.code}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              )
            }
          </Field>
        )}
        {division && (
          <Field label="Team" error={errors.subdivisionCode}>
            {(p) => (
              <Select
                {...p}
                value={team}
                onChange={(e) => {
                  setTeam(e.target.value);
                  emit({ team: e.target.value });
                }}
              >
                <option value="">All teams in {division.name}</option>
                {division.teams.map((t) => (
                  <option key={t.code} value={t.code}>
                    {t.name}
                    {t.isActive ? "" : " (switched off)"}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
      </div>
      <p className="rounded-[12px] bg-bench/60 px-3 py-2 text-meta text-ink-2">
        {personName} will be <strong className="font-semibold text-ink">{role?.name ?? "—"}</strong> {sentence}.
      </p>
    </div>
  );
}

export function initialAssignment(roles: Role[], divisions: OrgDivision[]): AssignmentInput {
  const first = divisions[0];
  return {
    roleKey: roles[0]?.key ?? "",
    moduleKey: first?.code ?? ALL,
    divisionCode: first && !first.spansDivisions ? first.code : null,
    subdivisionCode: null,
  };
}
