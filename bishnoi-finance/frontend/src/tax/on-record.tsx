import { Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import type { makeFormat } from "@/src/platform/lib/format";
import type { TaxHistoryEntry, TaxProfile } from "./types";

type Format = ReturnType<typeof makeFormat>;

/** "registered name", "registered name and TIN", "registered name, TIN and registered address". */
function inWords(parts: string[]): string {
  return parts.length < 2 ? (parts[0] ?? "") : `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`;
}

const notYet = <span className="font-semibold text-hema">Not filled in yet</span>;

/** The registration as it stands, at a glance: what every invoice will print. */
export function OnRecord({ profile, fmt, canEdit }: { profile: TaxProfile; fmt: Format; canEdit: boolean }) {
  return (
    <Sheet className="max-w-[50rem] px-5 py-5 sm:px-8">
      <SectionTitle action={<span className={`text-sm font-semibold ${profile.complete ? "text-ink-2" : "text-hema"}`}>{profile.complete ? "Complete" : "Incomplete"}</span>}>
        On record
      </SectionTitle>
      <Particulars
        items={[
          ["Registration type", profile.regimeName],
          ["Registered name", profile.registeredName || notYet],
          ["Trade name", profile.tradeName],
          ["TIN", profile.tin ? <span className="tabular-nums">{`${profile.tin}-${profile.branchCode}`}</span> : notYet],
          ["Registered address", profile.registeredAddress || notYet],
          ["Catalogue prices", profile.pricesIncludeTax ? "VAT-inclusive (shelf prices)" : "VAT-exclusive"],
        ]}
      />
      <p className="mt-4 text-meta text-ink-3">
        {profile.updatedByName ? `Last changed ${fmt.whenLabel(profile.updatedAt)} by ${profile.updatedByName}.` : "Not changed in Finance yet."}{" "}
        {canEdit ? "To change it, edit the boxes below and save." : "Only Finance administrators can change it."}
      </p>
    </Sheet>
  );
}

/** Each change to the registration: when, who, and which parts (the activity log keeps no values). */
export function RegistrationHistory({ history, fmt }: { history: TaxHistoryEntry[]; fmt: Format }) {
  const when = fmt.on({ dateStyle: "medium", timeStyle: "short" });
  return (
    <Sheet className="max-w-[50rem] px-5 py-5 sm:px-8">
      <SectionTitle>History</SectionTitle>
      {history.length === 0 ? (
        <p className="text-sm text-ink-3">No changes yet.</p>
      ) : (
        <ul className="divide-y divide-rule border-t border-rule text-sm">
          {history.map((h, i) => (
            <li key={`${h.at}-${i}`} className="grid gap-1 py-2 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4">
              <span className="text-ink-2 tabular-nums">{when.format(new Date(h.at))}</span>
              <span>
                <span className="font-semibold">{h.who}</span>{" "}
                {h.changed?.length ? `changed the ${inWords(h.changed)}` : "saved the registration"}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-meta text-ink-3">Shows which parts changed, not what they were. The last 20 changes.</p>
    </Sheet>
  );
}
