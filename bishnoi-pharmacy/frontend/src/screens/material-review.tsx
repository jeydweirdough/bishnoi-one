import { ExternalLink } from "lucide-react";
import { Particulars, PageHeader, SectionTitle, Sheet, Subheading } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { MaterialDecisionForm } from "../components/material-decision-form";
import { MaterialReviewMark, NoAccess, sourceName } from "../components/bits";
import { pageFor } from "../lib/page";
import type { MaterialReviewDetail } from "../lib/types";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { review } = await load<MaterialReviewDetail>(`/material-reviews/${enc(id)}`);
  return { title: `Review ${review.title}` };
}

/**
 * Review a promotional material: the design itself, what it is and what it
 * promotes, the earlier versions with the comments they got, and the decision.
 */
export default async function MaterialReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { fmt, allowed } = await pageFor("materials.view");
  if (!allowed) return <NoAccess what="promotional materials" />;
  const { id } = await params;
  const { review: r, earlier, canDecide } = await load<MaterialReviewDetail>(`/material-reviews/${enc(id)}`);
  const file = `/material-reviews/${r.id}/file`;
  const picture = r.contentType.startsWith("image/");

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/material-reviews", label: "Promotional materials" }]}
        title={
          <span className="inline-flex flex-wrap items-center gap-3">
            <span>{r.title}</span>
            <MaterialReviewMark status={r.status} />
          </span>
        }
      >
        {r.number} · version {r.version} · sent by {r.sentBy} from {sourceName(r.source)} {fmt.whenLabel(r.receivedAt).toLowerCase()}
        {r.reviewedBy && r.reviewedAt ? ` · reviewed ${fmt.whenLabel(r.reviewedAt).toLowerCase()} by ${r.reviewedBy}${r.reviewedByLicense ? ` (${r.reviewedByLicense})` : ""}` : ""}
      </PageHeader>

      {r.status !== "waiting" && r.comments && (
        <div role="note" className="mb-4 rounded-[3px] border border-rule-strong bg-sheet px-4 py-3 text-sm">
          <span className="font-semibold">Comments:</span> {r.comments}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="space-y-4">
          <Sheet className="px-5 py-5">
            <SectionTitle
              icon="approvals"
              action={
                <a href={file} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-meta font-semibold text-hema hover:underline">
                  Open design <ExternalLink className="size-3.5" aria-hidden />
                </a>
              }
            >
              Design
            </SectionTitle>
            <div className="mt-3 overflow-hidden rounded-[3px] border border-rule bg-bench/40">
              {picture ? (
                // eslint-disable-next-line @next/next/no-img-element -- the design as sent, through this app's own route
                <img src={file} alt={`Design of ${r.title}, version ${r.version}`} className="mx-auto max-h-[70vh] w-auto" />
              ) : (
                <iframe src={file} title={`Design of ${r.title}, version ${r.version}`} className="h-[70vh] w-full" />
              )}
            </div>
            <p className="mt-2 text-meta text-ink-3">{r.fileName}</p>
          </Sheet>

          <Sheet className="px-5 py-5">
            <SectionTitle icon="particulars">Details</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  ["Type", r.kind],
                  ["Product", r.product],
                  ["Description", r.description],
                  ["Changes in this version", r.notes],
                  ["Reference", r.reference],
                ]}
              />
            </div>
          </Sheet>

          {earlier.length > 0 && (
            <Sheet className="px-5 py-5">
              <SectionTitle icon="history">Earlier versions</SectionTitle>
              <ul className="-mx-5 mt-3 divide-y divide-rule border-t border-rule">
                {earlier.map((e) => (
                  <li key={e.id} className="px-5 py-3 text-sm">
                    <span className="flex flex-wrap items-center justify-between gap-2">
                      <a href={`/material-reviews/${e.id}`} className="font-semibold text-hema hover:underline">
                        Version {e.version}
                      </a>
                      <MaterialReviewMark status={e.status} />
                    </span>
                    {e.comments && <span className="mt-1 block text-ink-2">{e.comments}</span>}
                    <span className="mt-1 block text-meta text-ink-3">
                      {e.reviewedBy && e.reviewedAt ? `${e.reviewedBy} · ${fmt.whenLabel(e.reviewedAt)}` : fmt.whenLabel(e.receivedAt)}
                    </span>
                  </li>
                ))}
              </ul>
            </Sheet>
          )}
        </div>

        <Sheet className="h-fit px-5 py-5">
          <SectionTitle icon="approvals">Decision</SectionTitle>
          {canDecide ? (
            <div className="mt-4">
              <MaterialDecisionForm id={r.id} number={r.number} />
            </div>
          ) : r.status === "waiting" ? (
            <p className="mt-1 text-meta text-ink-3">A pharmacist approves or returns it. You can see where it stands.</p>
          ) : (
            <div className="mt-3">
              <Subheading>Next</Subheading>
              <p className="mt-1 text-meta text-ink-2">
                {r.status === "approved"
                  ? "Admin can now produce it and give it out."
                  : r.status === "returned"
                    ? "The marketing assistant corrects it in Admin; the new version comes in here for review."
                    : "It won't be produced."}
              </p>
            </div>
          )}
        </Sheet>
      </div>
    </>
  );
}
