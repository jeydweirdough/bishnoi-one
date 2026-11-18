import { accountSend } from "@/src/platform/lib/account";
import { AccessFrame } from "./frame";
import { loadAccess } from "./load";
import { PeopleList } from "./people";
import { RecycleBin } from "./recycle-bin";
import { AccessRolesEditor } from "./roles-editor";
import type { AbilityCatalogue, BinPerson, PersonPage } from "./types";
import { PersonPanel, type PanelLog } from "./person-panel";
import { logSources, readLog } from "@/src/one/company/activity";
import { said } from "@/src/one/company/screens";

// The Platform module's pages in the one app (decided 2026-10-23): people and
// access for the whole company, for its administrators.

export async function AccessPeople({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const data = await loadAccess();
  const search = await searchParams;
  const one = (k: string) => (typeof search[k] === "string" ? (search[k] as string) : "");
  const id = one("person") || null;
  // A person opens in a panel beside the list (2026-10-31, as Zoho Directory's Users).
  const row = id && data ? data.people.find((p) => p.id === id) : undefined;
  let panel = null;
  if (row && data) {
    const person = await accountSend<PersonPage>("GET", `/identity/access/people/${encodeURIComponent(row.id)}`).catch(() => null);
    if (person) {
      // Their own actions in Bishnoi One and every app (2026-11-18, step 4F), read only when the tab is open:
      // each source reads just this person's entries; "Older" keeps each source's place.
      const activity = one("tab") === "activity" ? await personLog(row.id, person.email, one) : null;
      panel = <PersonPanel key={row.id} person={person} row={row} data={data} activity={activity} />;
    }
  }
  return <AccessFrame current="people">{data && <PeopleList data={data} selected={row?.id ?? null} panel={panel} />}</AccessFrame>;
}

async function personLog(id: string, email: string, one: (k: string) => string): Promise<PanelLog> {
  const sources = await logSources();
  const before: Record<string, string> = Object.fromEntries(sources.map((s) => [s.key, one(`before_${s.key}`)]).filter(([, v]) => v));
  const link = (cursors: Record<string, string>) =>
    `/platform/roles/people?${new URLSearchParams({ person: id, tab: "activity", ...Object.fromEntries(Object.entries(cursors).map(([k, v]) => [`before_${k}`, v])) })}`;
  const skip = new Set(one("unavailable").split(",").filter(Boolean));
  const log = await readLog({ sources, before, q: "", category: "", here: link(before), skip, person: { id, email } });
  const labelOf = Object.fromEntries(sources.map((s) => [s.key, s.label]));
  return {
    entries: log.entries.map((e) => ({
      id: e.id,
      at: e.at,
      app: labelOf[e.source] ?? e.source,
      // Theirs, so their name isn't repeated on every line; the target only when it's someone or something else.
      text: `${said(e.action)}${e.target && e.target.toLowerCase() !== email.toLowerCase() ? `: ${e.target}` : ""}`,
      fields: e.fields,
    })),
    older: log.more ? link(log.next) : null,
    unavailable: log.unavailable,
  };
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
