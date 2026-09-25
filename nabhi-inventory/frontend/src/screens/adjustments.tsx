import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { adjustmentStep, countStep, withdrawAdjustment } from "../actions/inventory";
import { AdjustmentForm, CountSheet, StartCount } from "../components/adjust-forms";
import { AdjustTabs } from "../components/catalog-tabs";
import { RecordTools } from "../components/record-tools";
import { AdjustmentStamp, CountStamp } from "../components/stamps";
import { StepButton } from "../components/step-button";
import { Chips, Figures, NoAccess, RowLink, Table, Td, Trail } from "../components/ui";
import { param, query, signed } from "../lib/labels";
import { canAddFrom, context, type Params, type Search } from "../lib/page";
import type { Adjustment, AdjustmentBrief, BatchRow, Count, CountBrief, ReasonOption, Reference } from "../lib/types";

export async function AdjustmentsPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, at } = await context();
  if (!may("adjustments.view")) return <NoAccess what="adjustments" />;
  const status = param(await searchParams, "status");
  const rows = await load<AdjustmentBrief[]>(`/inventory/adjustments${query({ status })}`);
  const chip = (s: string, label: string) => ({ value: s, label, href: `/adjustments${query({ status: s })}` });
  return (
    <>
      <PageHeader
        title="Stock adjustments"
        actions={may("adjustments.create") && <LinkButton href="/adjustments/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New adjustment</LinkButton>}
      >
        When what&apos;s on the shelf doesn&apos;t match the system. Every one has a reason and goes on the trail.
        {!may("adjustments.approve") && may("adjustments.create") && " Yours wait for someone who may approve them."}
      </PageHeader>
      <AdjustTabs me={me} current="/adjustments" />
      <Chips label="Status" current={status} options={[chip("", "All"), chip("pending", "Waiting for approval"), chip("posted", "Posted"), chip("rejected", "Rejected")]} />
      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="adjustments" title="No adjustments here" />
        ) : (
          <Table head={["Adjustment", "Reason", "Warehouse", "Status", "Written by", " Units", " Value"]} min="52rem">
            {rows.map((a) => (
              <tr key={a.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/adjustments/${a.id}`} sub={at(a.createdAt)}>{a.number}</RowLink></Td>
                <Td>{a.reasonLabel}{a.countId && <span className="block text-meta text-ink-3">From a count</span>}</Td>
                <Td>{a.warehouse.code}</Td>
                <Td><AdjustmentStamp status={a.status} /></Td>
                <Td className="text-ink-2">{a.createdBy?.name ?? "—"}</Td>
                <Td num className="font-semibold">{signed(a.units, fmt.count)}</Td>
                <Td num>{fmt.peso(a.value)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function AdjustmentPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("adjustments.view")) return <NoAccess what="adjustments" />;
  const a = await load<Adjustment>(`/inventory/adjustments/${enc(id)}`);
  const pending = a.status === "pending";
  return (
    <>
      <PageHeader
        crumbs={[{ href: "/adjustments", label: "Adjustments" }]}
        title={a.number}
        tools={pending && may("adjustments.create") && <RecordTools what="adjustment" name={a.number} remove={withdrawAdjustment.bind(null, a.id)} after="/adjustments" removeNote="It hasn't been posted, so nothing in stock changes." />}
        actions={
          pending && may("adjustments.approve") && (
            <>
              <StepButton run={adjustmentStep.bind(null, a.id, "approve")} label="Approve & post" done={`${a.number} posted`} variant="primary" confirm={{ title: `Post ${a.number}?`, body: "Stock changes now, and the change is on the trail.", danger: false }} />
              <StepButton run={adjustmentStep.bind(null, a.id, "reject")} label="Reject" done={`${a.number} rejected`} variant="quiet" confirm={{ title: `Reject ${a.number}?`, body: "Nothing in stock changes.", danger: true }} />
            </>
          )
        }
      >
        <AdjustmentStamp status={a.status} /> <span className="ml-1">{a.reasonLabel} · {a.warehouse.name}</span>
        {a.countId && <> · from <Link href={`/counts/${a.countId}`} className="text-hema hover:underline">a count</Link></>}
      </PageHeader>
      <Sheet className="px-5 py-4">
        <Trail steps={[
          { label: "Written by", who: a.createdBy, when: at(a.createdAt) },
          { label: a.status === "rejected" ? "Rejected by" : "Approved & posted by", who: a.decidedBy, when: a.decidedAt ? at(a.decidedAt) : null },
        ]} />
        {a.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{a.notes}</p>}
      </Sheet>
      <Sheet className="mt-5">
        <Table head={["Product", "Location", "Batch", "Serial numbers", " Change", " Value"]}>
          {a.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
              <Td>{l.location.code}</Td>
              <Td className="font-mono">{l.batch ? <>{l.batch.batchNo}{l.batch.expiresOn && <span className="block font-sans text-meta text-ink-3">exp. {day(l.batch.expiresOn)}</span>}</> : "—"}</Td>
              <Td className="font-mono text-meta">{l.serials.join(", ") || "—"}</Td>
              <Td num className="font-semibold">{signed(l.quantity, fmt.count)}</Td>
              <Td num>{fmt.peso(l.value)}</Td>
            </tr>
          ))}
        </Table>
      </Sheet>
      {a.reason === "damaged" && <p className="mt-3 text-meta text-ink-3">Damaged stock stays on hand, set aside, until it&apos;s written off (reason: Written off).</p>}
    </>
  );
}

export async function NewAdjustmentPage({ searchParams }: { searchParams: Search }) {
  const { may } = await context();
  if (!may("adjustments.create")) return <NoAccess what="writing adjustments" />;
  const s = await searchParams;
  const [ref, reasons, batches] = await Promise.all([load<Reference>("/inventory/reference"), load<ReasonOption[]>("/inventory/adjustments/reasons"), load<BatchRow[]>("/inventory/batches")]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/adjustments", label: "Adjustments" }]} title="New adjustment">
        {may("adjustments.approve") ? "It's posted as soon as you save it." : "It waits for someone who may approve adjustments before stock changes."}
      </PageHeader>
      <AdjustmentForm canAdd={canAddFrom(may)} reference={ref} reasons={reasons} batches={batches} approves={may("adjustments.approve")} preset={{ reason: param(s, "reason"), warehouseId: param(s, "warehouse") }} />
    </>
  );
}

export async function CountsPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, at } = await context();
  if (!may("counts.view")) return <NoAccess what="inventory counts" />;
  const s = await searchParams;
  const status = param(s, "status");
  const [rows, ref] = await Promise.all([load<CountBrief[]>(`/inventory/counts${query({ status })}`), load<Reference>("/inventory/reference")]);
  return (
    <>
      <PageHeader title="Inventory counts">
        A physical count: the system writes down what it expects, people count what&apos;s there, and once approved every difference becomes an adjustment.
      </PageHeader>
      <AdjustTabs me={me} current="/counts" />
      {may("counts.create") && (
        <Sheet className="mb-5 px-5 py-4">
          <StartCount canAdd={canAddFrom(may)} reference={ref} warehouseId={param(s, "warehouse")} />
        </Sheet>
      )}
      <Sheet>
        {rows.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-ink-2">No counts yet.</div>
        ) : (
          <Table head={["Count", "Warehouse", "Status", " Counted", " Differences", " Units off", " Value off"]} min="52rem">
            {rows.map((c) => (
              <tr key={c.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/counts/${c.id}`} sub={`${at(c.createdAt)} · ${c.createdBy?.name ?? ""}`}>{c.number}</RowLink></Td>
                <Td>{c.warehouse.name}{c.category && <span className="block text-meta text-ink-3">{c.category.name} only</span>}</Td>
                <Td><CountStamp status={c.status} /></Td>
                <Td num>{c.countedCount} / {c.lineCount}</Td>
                <Td num>{c.varianceCount}</Td>
                <Td num className={c.varianceUnits ? "font-semibold text-eosin" : ""}>{signed(c.varianceUnits, fmt.count)}</Td>
                <Td num>{fmt.peso(c.varianceValue)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function CountPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("counts.view")) return <NoAccess what="inventory counts" />;
  const [c, ref] = await Promise.all([load<Count>(`/inventory/counts/${enc(id)}`), load<Reference>("/inventory/reference")]);
  const days = Object.fromEntries(c.lines.filter((l) => l.batch?.expiresOn).map((l) => [l.batch!.expiresOn!, day(l.batch!.expiresOn!)]));
  return (
    <>
      <PageHeader
        crumbs={[{ href: "/counts", label: "Inventory counts" }]}
        title={`${c.number} · ${c.warehouse.name}`}
        actions={
          <>
            {c.status === "submitted" && may("counts.approve") && (
              <>
                <StepButton
                  run={countStep.bind(null, c.id, "approve")}
                  label="Approve & adjust"
                  done={c.varianceCount ? "Approved: the differences are posted" : "Approved: nothing was off"}
                  variant="primary"
                  confirm={{ title: `Approve ${c.number}?`, body: c.varianceCount ? `${c.varianceCount} difference${c.varianceCount === 1 ? "" : "s"} (${signed(c.varianceUnits, fmt.count)} units, ${fmt.peso(c.varianceValue)}) will be posted as one adjustment.` : "Everything matched, so stock doesn't change.", danger: false }}
                />
                <StepButton run={countStep.bind(null, c.id, "reopen")} label="Send back to recount" done="Sent back for counting" />
              </>
            )}
            {(c.status === "open" || c.status === "submitted") && may("counts.create") && (
              <StepButton run={countStep.bind(null, c.id, "cancel")} label="Cancel count" done="Count cancelled" variant="quiet" confirm={{ title: `Cancel ${c.number}?`, body: "Nothing in stock changes.", danger: true }} />
            )}
          </>
        }
      >
        <CountStamp status={c.status} />
        {c.category && <span className="ml-1">{c.category.name} only</span>}
        {c.adjustmentId && <> · posted as <Link href={`/adjustments/${c.adjustmentId}`} className="text-hema hover:underline">an adjustment</Link></>}
      </PageHeader>
      <Figures
        items={[
          { label: "Lines", value: c.lineCount },
          { label: "Counted", value: `${c.countedCount} of ${c.lineCount}` },
          { label: "Differences", value: c.varianceCount, flag: c.varianceCount > 0 },
          { label: "Units off", value: signed(c.varianceUnits, fmt.count) },
          { label: "Value off", value: fmt.peso(c.varianceValue) },
          { label: "Started", value: <span className="text-sm">{at(c.createdAt)}</span> },
        ]}
      />
      <Sheet className="mt-5">
        <div className="px-5 pt-4"><SectionTitle icon="lists">Count sheet</SectionTitle></div>
        {c.lines.length === 0 ? (
          <p className="px-5 pb-4 text-meta text-ink-3">The system expected nothing here. Add anything you find.</p>
        ) : null}
        <CountSheet count={c} reference={ref} canCount={may("counts.create")} day={days} />
      </Sheet>
      <div className="mt-4">
        <Trail steps={[
          { label: "Started by", who: c.createdBy, when: at(c.createdAt) },
          { label: "Submitted by", who: c.submittedBy, when: null },
          { label: "Approved by", who: c.approvedBy, when: c.approvedAt ? at(c.approvedAt) : null },
        ]} />
      </div>
    </>
  );
}
