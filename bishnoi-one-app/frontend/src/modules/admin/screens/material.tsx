"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Archive, ExternalLink, Image as ImageIcon, Pencil, RefreshCw, Send, Trash2, Upload } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import {
  cancelDistribution,
  cancelProduction,
  checkAgain,
  deleteMaterial,
  productionReceived,
  recordDistributed,
  retireMaterial,
  submitForReview,
  uploadDesign,
  type MaterialPage,
  type Proof,
} from "@/src/modules/admin/actions/materials";
import { FormField, inputClass } from "@/src/modules/admin/components/executive-modals";
import { DateDialog, DistributionDialog, ProductionDialog } from "@/src/modules/admin/components/materials/material-dialogs";
import { MaterialForm } from "@/src/modules/admin/components/materials/material-form";
import { StageTracker, UrgencyBanner } from "@/src/modules/admin/components/materials/urgency";
import { DISTRIBUTION, MATERIAL_STATUS, PRODUCTION, REVIEW } from "@/src/modules/admin/components/materials/words";
import { day } from "@/src/modules/admin/components/operations/kinds";
import { Initials, Tag } from "@/src/modules/admin/components/record-table";
import { Button } from "@/src/modules/admin/platform/ui/button";
import { ConfirmButton } from "@/src/modules/admin/platform/ui/confirm";

type Dialog = null | "edit" | "produce" | "distribute" | { received: string } | { distributed: string };

/** A proof kept with a step, opened in a new tab. */
function ProofLink({ materialId, proof }: { materialId: string; proof: Proof }) {
  return (
    <a href={`/admin/materials/${materialId}/proofs/${proof.ref}`} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-[13px] font-medium text-ink underline">
      <ImageIcon className="size-3.5" aria-hidden /> Proof: {proof.name}
    </a>
  );
}

function Section({ title, count, action, children }: { title: string; count?: number; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-[22px] border border-rule bg-sheet px-5 py-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[17px] font-semibold text-ink">
          {title}
          {count !== undefined && <span className="ml-1.5 text-[12.5px] font-normal text-ink-3">{count}</span>}
        </h2>
        {action}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/**
 * One promotional material, as Admin's other record pages: the card with its
 * name, stage and the next step; then its design versions, production runs
 * and distributions, each with the actions this person may take; its history beside.
 */
export function MaterialScreen({ data: initial }: { data: MaterialPage }) {
  const router = useRouter();
  const [data, setData] = useState<MaterialPage>(initial);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [notes, setNotes] = useState("");
  const [pending, start] = useTransition();
  const { material: m, can } = data;
  const status = MATERIAL_STATUS[m.status];
  const latest = data.versions[0];
  // Timing words on the main button only when the date needed is close: "now" that means now.
  const soon = m.urgency.neededIn !== null && m.urgency.neededIn <= 15 ? " now" : "";

  function run(action: () => Promise<{ ok: true; data: MaterialPage } | { ok: false; error: string; fields?: Record<string, string> }>, done: string) {
    start(async () => {
      const r = await action();
      if (!r.ok) return void toast.error(r.fields ? Object.values(r.fields)[0] : r.error);
      setData(r.data);
      toast.success(done, { description: m.title });
    });
  }

  const main =
    can.submit ? (
      <Button variant="primary" disabled={pending} onClick={() => run(() => submitForReview(m.id), "Submitted for the pharmacist's review")}>
        <Send className="size-4" aria-hidden /> Submit for review{soon}
      </Button>
    ) : m.status === "pharmacy_review" ? (
      <Button disabled={pending} onClick={() => run(() => checkAgain(m.id), "Checked for an answer")}>
        <RefreshCw className="size-4" aria-hidden /> Check for an answer
      </Button>
    ) : can.produce && m.status === "approved" ? (
      <Button variant="primary" onClick={() => setDialog("produce")}>
        Order production{soon}
      </Button>
    ) : can.distribute ? (
      <Button variant="primary" onClick={() => setDialog("distribute")}>
        Request distribution
      </Button>
    ) : null;

  return (
    <>
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[13px] text-ink-3">
        <Link href="/admin/materials" className="hover:text-ink hover:underline">
          Promotional materials
        </Link>
        <span aria-hidden>›</span>
        <span className="truncate">{m.title}</span>
      </nav>

      <section className="mt-3 rounded-[22px] border-[1.5px] border-ink bg-sheet px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-start gap-4">
          <span className="origin-top-left scale-125 pt-0.5 sm:mr-2">
            <Initials name={m.title} filled />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-[1.75rem] leading-tight font-semibold tracking-[-0.02em] text-ink">{m.title}</h1>
              {can.edit && (
                <button suppressHydrationWarning type="button" onClick={() => setDialog("edit")} aria-label={`Change ${m.title}`} title="Change details" className="grid size-9 place-items-center rounded-full text-ink-3 hover:bg-mint hover:text-ink">
                  <Pencil className="size-4" aria-hidden />
                </button>
              )}
            </div>
            <p className="mt-0.5 text-[13.5px] text-ink-3">{[m.kind, m.product, m.no ? `No. ${m.no}` : null].filter(Boolean).join(" · ")}</p>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <Tag tone={status.tone} dot>
                {status.text}
              </Tag>
            </div>
          </div>
          {main}
        </div>

        <StageTracker material={m} distributed={data.distributions.some((d) => d.status === "distributed")} />
        <UrgencyBanner material={m} />

        <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-rule pt-4 sm:grid-cols-4">
          {[
            ["Design", latest ? `Version ${latest.number} · ${REVIEW[latest.review].text}` : "Not uploaded"],
            ["Quantity needed", m.quantity ? m.quantity.toLocaleString() : "Not set"],
            ["Date needed", day(m.neededBy) ?? "Not set"],
            ["In stock", m.reserved > 0 ? `${m.stock.toLocaleString()} · ${m.available.toLocaleString()} free` : m.stock.toLocaleString()],
            ["Size and specifications", m.specs ?? "Not set"],
            ["Budget", m.budget != null ? `₱${m.budget.toLocaleString("en-PH")}` : "Not set"],
            ["Added by", m.createdBy ?? "—"],
          ].map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-[12px] text-ink-3">{label}</dt>
              <dd className="truncate text-[13.5px] font-medium text-ink">{value}</dd>
            </div>
          ))}
        </dl>
        {m.description && <p className="mt-3 border-t border-rule pt-3 text-[13.5px] whitespace-pre-line text-ink-2">{m.description}</p>}
      </section>

      {(!data.linked.pharmacy || !data.linked.crm) && (
        <p role="note" className="mt-4 rounded-[14px] bg-[#fbf0d9] px-4 py-2.5 text-meta text-[#8a5a00]">
          Admin is not connected to {[!data.linked.pharmacy && "Pharmacy", !data.linked.crm && "the CRM"].filter(Boolean).join(" or ")} yet. Please contact your system administrator.
        </p>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-start">
        <div className="space-y-5">
          <Section title="Design" count={data.versions.length}>
            {can.upload && (
              <form
                className="mb-4 space-y-3 rounded-[16px] border border-dashed border-rule-strong p-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = new FormData(e.currentTarget);
                  const el = e.currentTarget;
                  run(async () => {
                    const r = await uploadDesign(m.id, form);
                    if (r.ok) {
                      el.reset();
                      setNotes("");
                    }
                    return r;
                  }, "Design uploaded");
                }}
              >
                <p className="text-[13.5px] text-ink-2">
                  {latest?.review === "draft"
                    ? `Replace version ${latest.number} before submitting it.`
                    : latest
                      ? `Upload version ${latest.number + 1}, corrected as the pharmacist asked.`
                      : "Upload the design as a PDF or a picture (PNG or JPG), up to 3 MB."}
                </p>
                <input suppressHydrationWarning name="file" type="file" accept="application/pdf,image/png,image/jpeg" required className="block w-full text-sm text-ink-2 file:mr-3 file:rounded-full file:border file:border-ink file:bg-sheet file:px-3.5 file:py-1.5 file:text-sm file:font-medium file:text-ink" />
                {latest && latest.review !== "draft" && (
                  <FormField label="What changed" optional>
                    <textarea suppressHydrationWarning name="notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={1000} placeholder="For the pharmacist: what was corrected" className={inputClass} />
                  </FormField>
                )}
                <Button type="submit" size="sm" disabled={pending}>
                  <Upload className="size-3.5" aria-hidden /> Upload design
                </Button>
              </form>
            )}
            {data.versions.length === 0 ? (
              <p className="text-[13.5px] text-ink-3">No design uploaded yet.</p>
            ) : (
              <ol className="divide-y divide-rule">
                {data.versions.map((v) => (
                  <li key={v.number} className="py-3 first:pt-0">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-ink">Version {v.number}</span>
                      <Tag tone={REVIEW[v.review].tone}>{REVIEW[v.review].text}</Tag>
                    </div>
                    {v.hasFile && (
                      <a href={`/admin/materials/${m.id}/versions/${v.number}/file`} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-[13px] font-medium text-ink underline">
                        {v.fileName ?? "Open design"} <ExternalLink className="size-3.5" aria-hidden />
                      </a>
                    )}
                    {v.notes && <p className="mt-1 text-[13px] text-ink-2">Changes: {v.notes}</p>}
                    {v.comments && (
                      <p className="mt-1.5 rounded-[12px] bg-bench px-3 py-2 text-[13px] text-ink">
                        <span className="font-medium">Pharmacist{v.reviewedBy ? ` (${v.reviewedBy})` : ""}:</span> {v.comments}
                      </p>
                    )}
                    <p className="mt-1 text-[12.5px] text-ink-3">
                      {v.sentAt ? `Submitted ${day(v.sentAt)}${v.sentBy ? ` by ${v.sentBy}` : ""}${v.pharmacyNumber ? ` · ${v.pharmacyNumber}` : ""}` : "Not submitted yet"}
                      {v.reviewedAt ? ` · reviewed ${day(v.reviewedAt)}` : ""}
                    </p>
                    {v.syncError && <p className="mt-1 text-[12.5px] text-danger">Last check: {v.syncError}</p>}
                  </li>
                ))}
              </ol>
            )}
          </Section>

          {(["approved", "in_production", "available", "retired"].includes(m.status) || data.productions.length > 0) && (
            <Section
              title="Production"
              count={data.productions.length}
              action={
                can.produce && (
                  <Button size="sm" onClick={() => setDialog("produce")}>
                    Order production
                  </Button>
                )
              }
            >
              {data.productions.length === 0 ? (
                <p className="text-[13.5px] text-ink-3">{can.produce ? "Order the first print run of the approved design." : "The executive office orders its production."}</p>
              ) : (
                <ul className="divide-y divide-rule">
                  {data.productions.map((p) => (
                    <li key={p.id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0">
                      <div className="min-w-0">
                        <p className="font-semibold text-ink">
                          {p.quantity.toLocaleString()} {p.supplier ? `from ${p.supplier}` : ""}
                        </p>
                        <p className="text-[12.5px] text-ink-3">
                          Version {p.versionNumber} · ordered {day(p.orderedOn) ?? "—"}
                          {p.expectedOn && p.status === "ordered" ? ` · expected ${day(p.expectedOn)}` : ""}
                          {p.receivedOn ? ` · received ${day(p.receivedOn)}` : ""}
                          {p.cost !== null ? ` · ₱${p.cost.toLocaleString("en-PH")}` : ""}
                          {p.by ? ` · ${p.by}` : ""}
                        </p>
                        {p.notes && <p className="mt-1 text-[13px] text-ink-2">{p.notes}</p>}
                        {p.proof && <ProofLink materialId={m.id} proof={p.proof} />}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Tag tone={PRODUCTION[p.status].tone}>{PRODUCTION[p.status].text}</Tag>
                        {can.produce && p.status === "ordered" && (
                          <>
                            <Button size="sm" variant="primary" onClick={() => setDialog({ received: p.id })}>
                              Mark received
                            </Button>
                            <ConfirmButton
                              label="Cancel"
                              triggerVariant="quiet"
                              triggerSize="sm"
                              title="Cancel this production run?"
                              body={`The order of ${p.quantity.toLocaleString()} is cancelled. Nothing is added to stock.`}
                              confirmLabel="Cancel production"
                              onConfirm={async () => {
                                const r = await cancelProduction(m.id, p.id);
                                if (!r.ok) return void toast.error(r.error), false;
                                setData(r.data);
                                toast.success("Production cancelled", { description: m.title });
                              }}
                            />
                          </>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}

          {(["available", "retired"].includes(m.status) || data.distributions.length > 0) && (
            <Section
              title="Distribution"
              count={data.distributions.length}
              action={
                can.distribute && (
                  <Button size="sm" onClick={() => setDialog("distribute")}>
                    Request distribution
                  </Button>
                )
              }
            >
              {data.distributions.length === 0 ? (
                <p className="text-[13.5px] text-ink-3">Ask to give some to a CRM team. Its manager approves the request in the CRM.</p>
              ) : (
                <ul className="divide-y divide-rule">
                  {data.distributions.map((d) => (
                    <li key={d.id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0">
                      <div className="min-w-0">
                        <p className="font-semibold text-ink">
                          {d.quantity.toLocaleString()} for {d.recipientName ? `${d.recipientName}, ${d.teamName}` : d.teamName}
                        </p>
                        <p className="text-[12.5px] text-ink-3">
                          Requested {day(d.requestedAt)}
                          {d.requestedBy ? ` by ${d.requestedBy}` : ""}
                          {d.managerName ? ` · ${d.status === "rejected" ? "rejected" : "approved"} by ${d.managerName}` : ""}
                          {d.distributedOn ? ` · given out ${day(d.distributedOn)}` : ""}
                        </p>
                        {d.purpose && <p className="mt-1 text-[13px] text-ink-2">{d.purpose}</p>}
                        {d.decisionNote && <p className="mt-1 text-[13px] text-ink-2">Manager&apos;s note: {d.decisionNote}</p>}
                        {d.proof && <ProofLink materialId={m.id} proof={d.proof} />}
                        {d.syncError && <p className="mt-1 text-[12.5px] text-danger">Last check: {d.syncError}</p>}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Tag tone={DISTRIBUTION[d.status].tone}>{DISTRIBUTION[d.status].text}</Tag>
                        {can.recordDistribution && d.status === "approved" && (
                          <Button size="sm" variant="primary" onClick={() => setDialog({ distributed: d.id })}>
                            Record as distributed
                          </Button>
                        )}
                        {can.recordDistribution && (d.status === "for_approval" || d.status === "approved") && (
                          <ConfirmButton
                            label="Cancel"
                            triggerVariant="quiet"
                            triggerSize="sm"
                            title="Cancel this request?"
                            body={`The request for ${d.quantity.toLocaleString()} is cancelled, and the CRM is told.`}
                            confirmLabel="Cancel request"
                            onConfirm={async () => {
                              const r = await cancelDistribution(m.id, d.id);
                              if (!r.ok) return void toast.error(r.error), false;
                              setData(r.data);
                              toast.success("Request cancelled", { description: m.title });
                            }}
                          />
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}
        </div>

        <div className="space-y-5">
          <Section title="History" count={data.history.length}>
            <ol className="space-y-3">
              {data.history.map((e) => (
                <li key={e.id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3">
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-medium text-ink">{e.text}</p>
                    <p className="text-[12.5px] text-ink-3">{e.by ?? "Bishnoi One"}</p>
                  </div>
                  <time dateTime={e.at} className="text-[12.5px] whitespace-nowrap text-ink-3">
                    {day(e.at.slice(0, 10))}
                  </time>
                </li>
              ))}
            </ol>
          </Section>

          {(can.retire || can.delete) && (
            <div className="flex flex-wrap gap-2">
              {can.retire && (
                <ConfirmButton
                  label="Retire material"
                  icon={<Archive className="size-4" aria-hidden />}
                  triggerVariant="quiet"
                  triggerSize="sm"
                  danger={false}
                  title={`Retire ${m.title}?`}
                  body="It is no longer given out. Its records and remaining stock stay."
                  confirmLabel="Retire"
                  onConfirm={async () => {
                    const r = await retireMaterial(m.id);
                    if (!r.ok) return void toast.error(r.error), false;
                    setData(r.data);
                    toast.success("Retired", { description: m.title });
                  }}
                />
              )}
              {can.delete && (
                <ConfirmButton
                  label="Delete material"
                  icon={<Trash2 className="size-4" aria-hidden />}
                  triggerVariant="quiet"
                  triggerSize="sm"
                  triggerClassName="!text-danger hover:!bg-danger/10"
                  title={`Delete ${m.title}?`}
                  body="The material, its designs and its history are deleted. This can't be undone."
                  confirmLabel="Delete material"
                  danger
                  onConfirm={async () => {
                    const r = await deleteMaterial(m.id);
                    if (!r.ok) return void toast.error(r.error), false;
                    toast.success("Deleted", { description: m.title });
                    router.push("/admin/materials");
                  }}
                />
              )}
            </div>
          )}
        </div>
      </div>

      {dialog === "edit" && <MaterialForm kinds={data.kinds} item={m} onClose={() => setDialog(null)} onSaved={setData} />}
      {dialog === "produce" && <ProductionDialog material={m} onClose={() => setDialog(null)} onDone={setData} />}
      {dialog === "distribute" && <DistributionDialog material={m} onClose={() => setDialog(null)} onDone={setData} />}
      {dialog && typeof dialog === "object" && "received" in dialog && (
        <DateDialog
          title="Mark production received"
          subtitle={m.title}
          label="Date received"
          proofHint="A photo of the delivery or the supplier's delivery receipt."
          confirm="Add to stock"
          onClose={() => setDialog(null)}
          onSave={async (form) => {
            const r = await productionReceived(m.id, dialog.received, form);
            if (!r.ok) return r.error;
            setData(r.data);
            toast.success("Received into stock", { description: m.title });
            return null;
          }}
        />
      )}
      {dialog && typeof dialog === "object" && "distributed" in dialog && (
        <DateDialog
          title="Record as distributed"
          subtitle={m.title}
          label="Date given out"
          proofHint="A photo of the hand-over or the receipt the team signed."
          confirm="Record"
          onClose={() => setDialog(null)}
          onSave={async (form) => {
            const r = await recordDistributed(m.id, dialog.distributed, form);
            if (!r.ok) return r.error;
            setData(r.data);
            toast.success("Recorded as distributed", { description: m.title });
            return null;
          }}
        />
      )}
    </>
  );
}
