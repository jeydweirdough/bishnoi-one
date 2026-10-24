import { PageHeader, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe, getFrame } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { SCREENS_BUILD, SCREENS_BUILT_AT, buildsDiffer } from "@/src/modules/finance/version/build";
import { RELEASES, VERSION } from "@/src/modules/finance/version/changes";

export const metadata = { title: "What's new" };

/** What changed in Finance, version by version, and which code is running now. */
export default async function WhatsNew() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  // The API's commit rides on the frame every page already asked for.
  const frame = (await getFrame()) as { build?: string | null; buildSource?: string | null };
  const apiBuild = frame.build ?? null;

  return (
    <>
      <PageHeader title="What's new">Finance is on version {VERSION}.</PageHeader>
      <div className="space-y-5">
        {RELEASES.map((r) => (
          <Sheet key={r.version} className="px-5 py-4">
            <SectionTitle icon="lists">
              Version {r.version}
              {r.date ? ` · ${fmt.dateLabel(r.date)}` : ""}
            </SectionTitle>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {r.changes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </Sheet>
        ))}

        <Sheet className="px-5 py-4">
          <SectionTitle icon="particulars">Which code is running</SectionTitle>
          <dl className="grid gap-x-8 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
            <dt className="text-ink-2">Screens</dt>
            <dd>{SCREENS_BUILD ? `${SCREENS_BUILD}${SCREENS_BUILT_AT ? `, built ${fmt.whenLabel(SCREENS_BUILT_AT)}` : ""}` : "Not known"}</dd>
            <dt className="text-ink-2">API</dt>
            <dd>{apiBuild ?? "Not known"}</dd>
          </dl>
          {buildsDiffer(apiBuild, frame.buildSource) && (
            <p className="mt-3 text-meta text-danger">The screens and the API were built from different code: an update may have reached only one of them.</p>
          )}
          <p className="mt-3 text-meta text-ink-3">&quot;-dirty&quot; means it was built with changes not yet saved to the code history (on a developer&apos;s computer).</p>
          <p className="mt-1 text-meta text-ink-3">The two are compared only once deployed: on a developer&apos;s computer the API restarts by itself when its code changes and the screens don&apos;t, so they often differ there without anything being wrong.</p>
        </Sheet>
      </div>
    </>
  );
}
