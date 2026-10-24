import type { FormLayout } from "@/src/platform/lib/types";

// Fields and customer types can be for some teams only (Settings → Forms,
// Settings → Customer types): the Rx team's customer form has its own. A
// record's team is its owner's, so the form follows who it's assigned to.
// A field can also be for some customer types only: a doctor is profiled, a
// hospital isn't asked a birthday.

type ForTeams = { onlyTeams?: string[]; exceptTeams?: string[]; onlyTypes?: string[]; exceptTypes?: string[] };

const within = (value: string | null, only: string[] = [], but: string[] = []) =>
  !(value && but.includes(value)) && (only.length === 0 || (value !== null && only.includes(value)));

/** Whether a field or type is on a record of this team (null: a record with no team). */
export function forTeam(item: ForTeams, teamId: string | null): boolean {
  return within(teamId, item.onlyTeams, item.exceptTeams);
}

/** Whether a field is on the form of a record of this team and, when given, this customer type. */
export function forRecord(item: ForTeams, teamId: string | null, kind?: string | null): boolean {
  return forTeam(item, teamId) && (kind === undefined || within(kind, item.onlyTypes, item.exceptTypes));
}

/** The form as this team (and customer type) fills it in: other fields left out, and sections left empty dropped. */
export function layoutForTeam(layout: FormLayout, teamId: string | null, kind?: string | null): FormLayout {
  return {
    ...layout,
    sections: layout.sections.map((s) => ({ ...s, fields: s.fields.filter((f) => forRecord(f, teamId, kind)) })).filter((s) => s.fields.length > 0),
  };
}
