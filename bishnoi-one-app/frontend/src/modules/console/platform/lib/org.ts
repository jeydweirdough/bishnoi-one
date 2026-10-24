import "server-only";
import { getCompanyMe, getMe, load } from "@/src/modules/console/platform/lib/api";
import { makeFormat, type Format } from "@/src/modules/console/platform/lib/format";
import type { CompanyLists, OrgDivision, OrgTeam } from "@/src/modules/console/platform/lib/types";

/**
 * How this company shows money, dates and times. Cheap from anywhere on the
 * server, however deep: /auth/me is fetched once a request, so a leaf sheet can
 * ask for it rather than having it handed down through every parent.
 */
export async function orgFormat(): Promise<Format> {
  return makeFormat((await getCompanyMe()).org);
}

/** The company's own pick-lists, as this session sees them: switched-on choices only. */
export async function orgLists(): Promise<CompanyLists> {
  return (await getMe()).lists;
}

export async function loadOrg(): Promise<OrgDivision[]> {
  return (await load<{ divisions: OrgDivision[] }>("/org")).divisions;
}

/** A division's teams, limited to the given codes, keeping the always-included one even if switched off. */
export async function teamsFor(division: string, codes: string[], keep?: string): Promise<OrgTeam[]> {
  const org = await loadOrg();
  const teams = org.find((d) => d.code === division)?.teams ?? [];
  return teams.filter((t) => t.code === keep || (t.isActive && codes.includes(t.code)));
}

/** The teams a customer may be put in, across every division the person sells
 *  in. Each says which division it is in, because a team code alone doesn't. */
export async function pickableTeams(
  wanted: { division: string; code: string }[],
  keep?: { division: string; team: string },
): Promise<(OrgTeam & { division: string; divisionName: string })[]> {
  const org = await loadOrg();
  const allowed = new Set(wanted.map((t) => `${t.division}:${t.code}`));
  return org.flatMap((d) =>
    d.teams
      .filter(
        (t) =>
          (keep && keep.division === d.code && keep.team === t.code) ||
          (t.isActive && allowed.has(`${d.code}:${t.code}`)),
      )
      .map((t) => ({ ...t, division: d.code, divisionName: d.name })),
  );
}
