import { accountSend } from "@/src/platform/lib/account";
import { AccessFrame } from "./frame";
import { loadAccess } from "./load";
import { PeopleList } from "./people";
import { RecycleBin } from "./recycle-bin";
import { AccessRolesEditor } from "./roles-editor";
import type { AbilityCatalogue, BinPerson } from "./types";

// The Platform module's pages in the one app (decided 2026-10-23): people and
// access for the whole company, for its administrators.

export async function AccessPeople() {
  const data = await loadAccess();
  return <AccessFrame current="people">{data && <PeopleList data={data} />}</AccessFrame>;
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
