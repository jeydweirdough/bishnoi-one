import { accountSend } from "@/src/platform/lib/account";
import { AccessFrame } from "./frame";
import { loadAccess } from "./load";
import { PeopleList } from "./people";
import { RecycleBin } from "./recycle-bin";
import { AccessRolesEditor } from "./roles-editor";
import type { AbilityCatalogue, BinPerson, PersonPage } from "./types";
import { PersonPanel } from "./person-panel";
import { said } from "@/src/one/company/screens";

// The Platform module's pages in the one app (decided 2026-10-23): people and
// access for the whole company, for its administrators.

export async function AccessPeople({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const data = await loadAccess();
  const asked = (await searchParams).person;
  const id = typeof asked === "string" ? asked : null;
  // A person opens in a panel beside the list (2026-10-31, as Zoho Directory's Users).
  const row = id && data ? data.people.find((p) => p.id === id) : undefined;
  let panel = null;
  if (row && data) {
    const person = await accountSend<PersonPage>("GET", `/identity/access/people/${encodeURIComponent(row.id)}`).catch(() => null);
    if (person) {
      const activity = person.activity.map((e) => ({
        id: e.id,
        at: e.at,
        text: `${e.actor} ${said(e.action).toLowerCase()}${e.target ? `: ${e.target}` : ""}`,
      }));
      panel = <PersonPanel key={row.id} person={person} row={row} data={data} activity={activity} />;
    }
  }
  return <AccessFrame current="people">{data && <PeopleList data={data} selected={row?.id ?? null} panel={panel} />}</AccessFrame>;
}

export async function AccessRoles() {
  const data = await loadAccess();
  // Bishnoi One's abilities and job roles (step 6); the editor still works without them.
  const catalogue = data ? await accountSend<AbilityCatalogue>("GET", "/identity/access/abilities").catch(() => null) : null;
  return <AccessFrame current="roles">{data && <AccessRolesEditor data={data} catalogue={catalogue} />}</AccessFrame>;
}

/** The people deleted to the recycle bin (2026-10-30), each restorable. */
export async function AccessRecycleBin() {
  const data = await loadAccess();
  const bin = data ? await accountSend<{ people: BinPerson[] }>("GET", "/identity/access/bin").catch(() => null) : null;
  return <AccessFrame current="bin">{bin && <RecycleBin people={bin.people} />}</AccessFrame>;
}
