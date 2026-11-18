import Link from "next/link";
import { accountSend } from "@/src/platform/lib/account";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { HrRecordsView } from "./hr-records";
import { AccessFrame } from "./frame";
import { loadAccess } from "./load";
import { PeopleList } from "./people";
import { RecycleBin } from "./recycle-bin";
import { AccessRolesEditor } from "./roles-editor";
import type { AbilityCatalogue, BinPerson, HrPerson, HrRecords, PersonPage } from "./types";
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
      // HR records (step 4I): read only when their tab is opened (each reading is in the activity log).
      const hr = one("tab") === "hr" && data.hrRecords ? await accountSend<HrRecords>("GET", `/identity/access/people/${encodeURIComponent(row.id)}/hr`).catch(() => null) : null;
      panel = <PersonPanel key={row.id} person={person} row={row} data={data} activity={activity} hr={hr} />;
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

/**
 * HR records on their own (step 4I), for HR who aren't the company's administrators: the employees on the left,
 * the one picked on the right. Administrators use the HR records tab on Employees.
 */
export async function HrRecordsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const search = await searchParams;
  const id = typeof search.person === "string" ? search.person : null;
  const list = await accountSend<{ people: HrPerson[] }>("GET", "/identity/access/hr/people").catch(() => null);
  if (!list) {
    return (
      <>
        <PageHeader title="HR records" />
        <Sheet>
          <Empty icon="people" title="Only HR and administrators see HR records">
            Ask your company&apos;s administrator for the Manage HR records ability.
          </Empty>
        </Sheet>
      </>
    );
  }
  const person = id ? list.people.find((p) => p.id === id) : undefined;
  const records = person ? await accountSend<HrRecords>("GET", `/identity/access/people/${encodeURIComponent(person.id)}/hr`).catch(() => null) : null;
  return (
    <>
      <PageHeader title="HR records">Each employee&apos;s details and documents. Only HR and administrators see them.</PageHeader>
      <div className="grid gap-5 lg:grid-cols-[18rem_1fr]">
        <Sheet className="max-h-[70vh] overflow-y-auto p-2">
          <ul>
            {list.people.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/platform/hr?person=${encodeURIComponent(p.id)}`}
                  aria-current={p.id === person?.id ? "page" : undefined}
                  className={`block rounded-lg px-3 py-2 ${p.id === person?.id ? "bg-bench" : "hover:bg-bench"}`}
                >
                  <span className="block truncate text-sm font-semibold text-ink">{p.fullName}</span>
                  <span className="block truncate text-meta text-ink-3">{p.title ?? p.email}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Sheet>
        <Sheet className="px-6 py-5">
          {person && records ? (
            <>
              <h2 className="mb-1 text-lg font-semibold text-ink">{person.fullName}</h2>
              <p className="mb-5 text-sm text-ink-3">{person.email}</p>
              <HrRecordsView key={person.id} personId={person.id} name={person.fullName} records={records} />
            </>
          ) : (
            <Empty icon="people" title="Choose an employee">
              Their details and documents open here.
            </Empty>
          )}
        </Sheet>
      </div>
    </>
  );
}
