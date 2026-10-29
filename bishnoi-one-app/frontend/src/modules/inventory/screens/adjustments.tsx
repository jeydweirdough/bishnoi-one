import { DocumentHeaderStrip } from "@/src/platform/ui/document-header";
import { HeaderFilters, type OperationTypeRow } from "@/src/modules/inventory/components/document-header";
import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { load, loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { adjustmentStep, countStep, withdrawAdjustment } from "@/src/modules/inventory/actions/inventory";
import { AdjustmentForm, CountSheet, StartCount } from "@/src/modules/inventory/components/adjust-forms";
import { CountSchedules } from "@/src/modules/inventory/components/count-schedules";
import { CountByScan } from "@/src/modules/inventory/components/scan";
import { RecordTools } from "@/src/modules/inventory/components/record-tools";
import { AdjustmentStamp, CountStamp } from "@/src/modules/inventory/components/stamps";
import { StepButton } from "@/src/modules/inventory/components/step-button";
import { Chips, Figures, Filters, NoAccess, RowLink, Table, Td, Trail } from "@/src/modules/inventory/components/ui";
import { param, query, signed } from "@/src/modules/inventory/lib/labels";
import { NeedsFirst } from "@/src/modules/inventory/components/setup";
import { loadSetup } from "@/src/modules/inventory/lib/setup";
import { Pager } from "@/src/modules/inventory/platform/ui/pager";
import { canAddFrom, context, keepInRange, paging, type Params, type Search } from "@/src/modules/inventory/lib/page";
import { given, referenceOf } from "@/src/modules/inventory/lib/reference";
import type { Adjustment, AdjustmentBrief, BatchRow, Count, CountBrief, CountSchedule, Paged, ReasonOption, Reference } from "@/src/modules/inventory/lib/types";

export async function AdjustmentsPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, at } = await context();
  if (!may("adjustments.view")) return <NoAccess what="adjustments" />;
  const s = await searchParams;
  const status = param(s, "status");
  const h = { operationType: param(s, "operationType"), timing: param(s, "timing") };
  const { page, size, vars } = paging(s);
  const base = `/inventory/adjustments${query({ status, ...h })}`;
  const { adjustments: list, operationTypes } = await loadQuery<{ adjustments: Paged<AdjustmentBrief>; operationTypes: OperationTypeRow[] }>(
    `query Adjustments($status: String, $operationType: String, $timing: String, $limit: Int, $offset: Int) { adjustments(status: $status, operationType: $operationType, timing: $timing, limit: $limit, offset: $offset) operationTypes }`,
    { ...(status ? { status } : {}), ...given(h), ...vars },
    ["adjustments", "operationTypes"],
  );
  keepInRange(list.items.length, list.total, page, base);
  const rows = list.items;
  const chip = (s: string, label: string) => ({ value: s, label, href: `/inventory/adjustments${query({ status: s })}` });
  return (
    <>
      <PageHeader
        title="Inventory adjustments"
        actions={may("adjustments.create") && <LinkButton href="/inventory/adjustments/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New adjustment</LinkButton>}
      >
        Corrects stock when the physical quantity differs from the system. Each adjustment needs a reason and is recorded in stock movements.
        {!may("adjustments.approve") && may("adjustments.create") && " Adjustments you create need approval before they are posted."}
      </PageHeader>
      <Chips label="Status" current={status} options={[chip("", "All"), chip("pending", "Pending approval"), chip("posted", "Posted"), chip("rejected", "Rejected")]} />
      <Filters keep={{ status }}>
        <HeaderFilters types={operationTypes} kinds={["adjustment"]} operationType={h.operationType} timing={h.timing} />
      </Filters>
      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="adjustments" title="No inventory adjustments" />
        ) : (
          <Table head={["Adjustment", "Reason", "Warehouse", "Status", "Created by", " Units", " Value"]} min="52rem">
            {rows.map((a) => (
              <tr key={a.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/inventory/adjustments/${a.id}`} sub={at(a.createdAt)}>{a.number}</RowLink></Td>
                <Td>{a.reasonLabel}{a.countId && <span className="block text-meta text-ink-3">From an inventory count</span>}</Td>
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
      <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "adjustment" : "adjustments"} />
    </>
  );
}

export async function AdjustmentPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("adjustments.view")) return <NoAccess what="adjustments" />;
  const { adjustment: a } = await loadQuery<{ adjustment: Adjustment }>(`query Adjustment($id: String!) { adjustment(id: $id) }`, { id }, ["adjustment"]);
  const pending = a.status === "pending";
  return (
    <>
      <PageHeader
        crumbs={[{ href: "/inventory/adjustments", label: "Inventory adjustments" }]}
        title={a.number}
        tools={pending && may("adjustments.create") && <RecordTools what="adjustment" name={a.number} remove={withdrawAdjustment.bind(null, a.id)} after="/inventory/adjustments" removeNote="It hasn't been posted, so nothing in stock changes." />}
        actions={
          pending && may("adjustments.approve") && (
            <>
              <StepButton run={adjustmentStep.bind(null, a.id, "approve")} label="Approve and post" done={`${a.number} posted`} variant="primary" confirm={{ title: `Post ${a.number}?`, body: "Stock is updated and the change is recorded in stock movements.", danger: false }} />
              <StepButton run={adjustmentStep.bind(null, a.id, "reject")} label="Reject" done={`${a.number} rejected`} variant="quiet" confirm={{ title: `Reject ${a.number}?`, body: "Nothing in stock changes.", danger: true }} />
            </>
          )
        }
      >
        <AdjustmentStamp status={a.status} /> <span className="ml-1">{a.reasonLabel} · {a.warehouse.name}</span>
        {a.countId && <> · from <Link href={`/inventory/counts/${a.countId}`} className="text-ink hover:underline">a count</Link></>}
      </PageHeader>
      <DocumentHeaderStrip header={a.header} source={a.countId && a.header.sourceDocument ? <Link href={`/inventory/counts/${a.countId}`} className="hover:underline">{a.header.sourceDocument}</Link> : undefined} />
      <Sheet className="px-5 py-4">
        <Trail steps={[
          { label: "Created by", who: a.createdBy, when: at(a.createdAt) },
          { label: a.status === "rejected" ? "Rejected by" : "Approved and posted by", who: a.decidedBy, when: a.decidedAt ? at(a.decidedAt) : null },
        ]} />
        {a.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{a.notes}</p>}
      </Sheet>
      <Sheet className="mt-5">
        <Table head={["Product", "Location", "Batch", "Serial numbers", " Change", " Value"]}>
          {a.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/inventory/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
              <Td>{l.location.code}</Td>
              <Td className="font-mono">{l.batch ? <>{l.batch.batchNo}{l.batch.expiresOn && <span className="block font-sans text-meta text-ink-3">exp. {day(l.batch.expiresOn)}</span>}</> : "—"}</Td>
              <Td className="font-mono text-meta">{l.serials.join(", ") || "—"}</Td>
              <Td num className="font-semibold">{signed(l.quantity, fmt.count)}</Td>
              <Td num>{fmt.peso(l.value)}</Td>
            </tr>
          ))}
        </Table>
      </Sheet>
      {a.reason === "damaged" && <p className="mt-3 text-meta text-ink-3">Damaged stock stays on hand, held separately, until it is written off (reason: Written off).</p>}
    </>
  );
}

export async function NewAdjustmentPage({ searchParams }: { searchParams: Search }) {
  const { may } = await context();
  if (!may("adjustments.create")) return <NoAccess what="creating adjustments" />;
  // What this page needs first; if any is missing, that instead of a form that can't be finished.
  const gate = NeedsFirst({ setup: await loadSetup(), needs: ["warehouse", "product"], then: "/inventory/adjustments/new", title: "New adjustment", doing: "adjust stock", crumbs: [{ href: "/inventory/adjustments", label: "Inventory adjustments" }], may });
  if (gate) return gate;
  const s = await searchParams;
  const { reference: ref, reasons, batches } = await loadQuery<{ reference: Pick<Reference, "products" | "units" | "warehouses">; reasons: ReasonOption[]; batches: BatchRow[] }>(
    `query NewAdjustment { ${referenceOf("products", "units", "warehouses")} reasons: adjustmentReasons batches }`,
    {},
    ["reference", "reasons", "batches"],
  );
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/adjustments", label: "Inventory adjustments" }]} title="New inventory adjustment">
        {may("adjustments.approve") ? "Stock is updated when you save." : "Requires approval before stock is updated."}
      </PageHeader>
      <AdjustmentForm canAdd={canAddFrom(may)} reference={ref} reasons={reasons} batches={batches} approves={may("adjustments.approve")} preset={{ reason: param(s, "reason"), warehouseId: param(s, "warehouse") }} />
    </>
  );
}

export async function CountsPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, at, day } = await context();
  if (!may("counts.view")) return <NoAccess what="inventory counts" />;
  const s = await searchParams;
  const status = param(s, "status");
  const h = { operationType: param(s, "operationType"), timing: param(s, "timing") };
  const { page, size, vars } = paging(s);
  const base = `/inventory/counts${query({ status, ...h })}`;
  const { counts: list, reference: ref, operationTypes } = await loadQuery<{ counts: Paged<CountBrief>; reference: Pick<Reference, "categories" | "warehouses">; operationTypes: OperationTypeRow[] }>(
    `query Counts($status: String, $operationType: String, $timing: String, $limit: Int, $offset: Int) { counts(status: $status, operationType: $operationType, timing: $timing, limit: $limit, offset: $offset) ${referenceOf("categories", "warehouses")} operationTypes }`,
    { ...(status ? { status } : {}), ...given(h), ...vars },
    ["counts", "reference", "operationTypes"],
  );
  keepInRange(list.items.length, list.total, page, base);
  const rows = list.items;
  // Cycle count schedules (step 14b): due ones first.
  const schedules = await load<{ items: CountSchedule[]; due: number }>("/inventory/count-schedules");
  return (
    <>
      <PageHeader title="Inventory counts">
        Physical inventory counts. Counted quantities are compared with system quantities, and on approval each variance is posted as an adjustment.
      </PageHeader>
      <Filters keep={{ status }}>
        <HeaderFilters types={operationTypes} kinds={["count"]} operationType={h.operationType} timing={h.timing} />
      </Filters>
      <Sheet className="mb-5 px-5 py-4">
        <CountSchedules
          schedules={schedules.items.map((x) => ({ ...x, nextLabel: day(x.nextOn), lastLabel: x.lastCountedOn ? day(x.lastCountedOn) : null }))}
          reference={ref}
          may={{ create: may("counts.create"), manage: may("counts.approve") }}
        />
      </Sheet>
      {may("counts.create") && (
        <Sheet className="mb-5 px-5 py-4">
          <StartCount canAdd={canAddFrom(may)} reference={ref} warehouseId={param(s, "warehouse")} />
        </Sheet>
      )}
      <Sheet>
        {rows.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-ink-2">No inventory counts.</div>
        ) : (
          <Table head={["Count", "Warehouse", "Status", " Counted", " Variances", " Variance units", " Variance value"]} min="52rem">
            {rows.map((c) => (
              <tr key={c.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/inventory/counts/${c.id}`} sub={`${at(c.createdAt)} · ${c.createdBy?.name ?? ""}`}>{c.number}</RowLink></Td>
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
      <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "count" : "counts"} />
    </>
  );
}

export async function CountPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("counts.view")) return <NoAccess what="inventory counts" />;
  const { count: c, reference: ref } = await loadQuery<{ count: Count; reference: Pick<Reference, "products"> }>(
    `query Count($id: String!) { count(id: $id) ${referenceOf("products")} }`,
    { id },
    ["count", "reference"],
  );
  const days = Object.fromEntries(c.lines.filter((l) => l.batch?.expiresOn).map((l) => [l.batch!.expiresOn!, day(l.batch!.expiresOn!)]));
  return (
    <>
      <PageHeader
        crumbs={[{ href: "/inventory/counts", label: "Inventory counts" }]}
        title={`${c.number} · ${c.warehouse.name}`}
        actions={
          <>
            {c.status === "submitted" && may("counts.approve") && (
              <>
                <StepButton
                  run={countStep.bind(null, c.id, "approve")}
                  label="Approve and adjust"
                  done={c.varianceCount ? "Approved; variances posted" : "Approved; no variances"}
                  variant="primary"
                  confirm={{ title: `Approve ${c.number}?`, body: c.varianceCount ? `${c.varianceCount} variance${c.varianceCount === 1 ? "" : "s"} (${signed(c.varianceUnits, fmt.count)} units, ${fmt.peso(c.varianceValue)}) will be posted as one adjustment.` : "No variances, so stock is unchanged.", danger: false }}
                />
                <StepButton run={countStep.bind(null, c.id, "reopen")} label="Return for recount" done="Returned for recount" />
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
        {c.adjustmentId && <> · posted as <Link href={`/inventory/adjustments/${c.adjustmentId}`} className="text-ink hover:underline">an adjustment</Link></>}
      </PageHeader>
      <DocumentHeaderStrip header={c.header} />
      <Figures
        items={[
          { label: "Lines", value: c.lineCount },
          { label: "Counted", value: `${c.countedCount} of ${c.lineCount}` },
          { label: "Variances", value: c.varianceCount, flag: c.varianceCount > 0 },
          { label: "Variance units", value: signed(c.varianceUnits, fmt.count) },
          { label: "Variance value", value: fmt.peso(c.varianceValue) },
          { label: "Started", value: <span className="text-sm">{at(c.createdAt)}</span> },
        ]}
      />
      {/* Count by scanning (step 14c): each scan adds one to the item's line. */}
      {c.status === "open" && may("counts.create") && (
        <Sheet className="mt-5 px-5 py-4">
          <CountByScan countId={c.id} />
        </Sheet>
      )}
      <Sheet className="mt-5">
        <div className="px-5 pt-4"><SectionTitle icon="lists">Count sheet</SectionTitle></div>
        {c.lines.length === 0 ? (
          <p className="px-5 pb-4 text-meta text-ink-3">No system quantities for this count. Add any items found.</p>
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
