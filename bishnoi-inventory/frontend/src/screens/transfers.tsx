import { ArrowRight, Plus } from "lucide-react";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { deleteTransfer, transferStep } from "../actions/inventory";
import { TransferForm } from "../components/document-forms";
import { PickForm, type PickLine } from "../components/pick-form";
import { ReceiveTransfer } from "../components/receive-transfer";
import { RecordTools } from "../components/record-tools";
import { TransferStamp } from "../components/stamps";
import { StepButton } from "../components/step-button";
import { Chips, Filters, NoAccess, RowLink, Table, Td, Trail } from "../components/ui";
import { param, query } from "../lib/labels";
import { canAddFrom, context, type Params, type Search } from "../lib/page";
import { batchChoices, given, referenceOf } from "../lib/reference";
import type { BatchRow, Reference, Transfer, TransferBrief } from "../lib/types";

export async function TransfersPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, at } = await context();
  if (!may("transfers.view")) return <NoAccess what="transfers" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), status: param(s, "status") };
  const { transfers } = await loadQuery<{ transfers: TransferBrief[] }>(`query Transfers($q: String, $status: String) { transfers(q: $q, status: $status) }`, given(f), ["transfers"]);
  const chip = (status: string, label: string) => ({ value: status, label, href: `/transfers${query({ q: f.q, status })}` });
  return (
    <>
      <PageHeader
        title="Stock transfers"
        actions={may("transfers.create") && <LinkButton href="/transfers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New transfer</LinkButton>}
      >
        Moving stock between warehouses: requested, approved, dispatched, in transit, received.
      </PageHeader>
      <Chips label="Status" current={f.status} options={[chip("", "All"), chip("draft", "Drafts"), chip("requested", "Requested"), chip("approved", "Approved"), chip("in_transit", "In transit"), chip("received", "Received"), chip("cancelled", "Cancelled")]} />
      <Filters q={f.q} placeholder="Transfer number" keep={{ status: f.status }} />
      <Sheet>
        {transfers.length === 0 ? (
          <Empty icon="transfers" title="No transfers here" />
        ) : (
          <Table head={["Transfer", "From → to", "Status", "Requested", "Dispatched", "Received", " Units"]} min="52rem">
            {transfers.map((t) => (
              <tr key={t.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/transfers/${t.id}`} sub={`${t.lineCount} line${t.lineCount === 1 ? "" : "s"}`}>{t.number}</RowLink></Td>
                <Td className="whitespace-nowrap">{t.from.code} <ArrowRight className="inline size-3.5 text-ink-3" aria-label="to" /> {t.to.code}</Td>
                <Td><TransferStamp status={t.status} /></Td>
                <Td className="text-meta text-ink-2">{at(t.requestedAt)}</Td>
                <Td className="text-meta text-ink-2">{at(t.dispatchedAt)}</Td>
                <Td className="text-meta text-ink-2">{at(t.receivedAt)}</Td>
                <Td num>{fmt.count(t.units)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function TransferPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("transfers.view")) return <NoAccess what="transfers" />;
  const { transfer: t, reference: ref } = await loadQuery<{ transfer: Transfer; reference: Pick<Reference, "warehouses"> }>(
    `query Transfer($id: String!) { transfer(id: $id) ${referenceOf("warehouses")} }`,
    { id },
    ["transfer", "reference"],
  );
  const pending = t.status === "draft" || t.status === "requested";
  // The batches each batch-tracked line could leave from: the sending
  // warehouse's batches in one read, rather than one per line.
  const dispatching = t.status === "approved" && may("transfers.dispatch");
  const { batches } = dispatching && t.lines.some((l) => l.product.trackBatches)
    ? await loadQuery<{ batches: BatchRow[] }>(`query Batches($w: String) { batches(warehouse: $w) }`, { w: t.from.id }, ["batches"])
    : { batches: [] as BatchRow[] };
  const pickLines: PickLine[] = dispatching
    ? t.lines.map((l) => ({ id: l.id, product: l.product, quantity: l.quantity, batches: l.product.trackBatches ? batchChoices(batches, l.product.id, day) : [] }))
    : [];
  const destination = ref.warehouses.find((w) => w.id === t.to.id)?.locations.filter((l) => l.isActive) ?? [];

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/transfers", label: "Transfers" }]}
        title={t.number}
        tools={pending && (
          <RecordTools what="transfer" name={t.number} editHref={may("transfers.create") ? `/transfers/${t.id}/edit` : undefined} remove={t.status === "draft" && may("transfers.create") ? deleteTransfer.bind(null, t.id) : undefined} after="/transfers" />
        )}
        actions={
          <>
            {t.status === "draft" && may("transfers.create") && <StepButton run={transferStep.bind(null, t.id, "request")} label="Request it" done="Transfer requested" />}
            {pending && may("transfers.approve") && <StepButton run={transferStep.bind(null, t.id, "approve")} label="Approve" done="Transfer approved" variant="primary" />}
            {(pending ? may("transfers.create") : t.status === "approved" && may("transfers.approve")) && (
              <StepButton run={transferStep.bind(null, t.id, "cancel")} label="Cancel transfer" done="Transfer cancelled" variant="quiet" confirm={{ title: `Cancel ${t.number}?`, danger: true }} />
            )}
          </>
        }
      >
        <TransferStamp status={t.status} /> <span className="ml-1">{t.from.name} → {t.to.name}</span>
      </PageHeader>

      <Sheet className="px-5 py-4">
        <Trail steps={[
          { label: "Requested by", who: t.requestedBy ?? t.createdBy, when: at(t.requestedAt ?? t.createdAt) },
          { label: "Approved by", who: t.approvedBy, when: t.approvedAt ? at(t.approvedAt) : null },
          { label: "Dispatched by", who: t.dispatchedBy, when: t.dispatchedAt ? at(t.dispatchedAt) : null },
          { label: "Received by", who: t.receivedBy, when: t.receivedAt ? at(t.receivedAt) : null },
        ]} />
        {t.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{t.notes}</p>}
      </Sheet>

      <Sheet className="mt-5">
        <Table head={["Product", " Quantity", ...(pending || t.status === "approved" ? [` Free in ${t.from.code}`] : ["Batches sent"])]}>
          {t.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
              <Td num>{fmt.count(l.quantity)} {l.product.unit}</Td>
              {l.available !== null ? (
                <Td num className={l.available < l.quantity ? "font-semibold text-eosin" : "text-ink-2"}>{fmt.count(l.available)}</Td>
              ) : (
                <Td className="text-meta text-ink-2">
                  {l.picks.map((p, i) => <span key={i} className="block">{p.quantity}{p.batchNo ? ` · ${p.batchNo}` : ""}{p.expiresOn ? ` (exp. ${day(p.expiresOn)})` : ""}</span>)}
                  {l.serials.length > 0 && <span className="block font-mono">{l.serials.join(", ")}</span>}
                </Td>
              )}
            </tr>
          ))}
        </Table>
      </Sheet>

      {t.status === "approved" && may("transfers.dispatch") && (
        <Sheet className="mt-6 px-5 pt-4 pb-5">
          <SectionTitle icon="transfers">Dispatch</SectionTitle>
          <p className="mb-3 text-meta text-ink-3">It leaves {t.from.name} now and is in transit until {t.to.name} receives it.</p>
          <PickForm kind="transfer" documentId={t.id} lines={pickLines} label="Dispatch" />
        </Sheet>
      )}
      {t.status === "in_transit" && may("transfers.receive") && (
        <Sheet className="mt-6 px-5 pt-4 pb-5">
          <SectionTitle icon="receiving">It arrived</SectionTitle>
          <p className="mb-3 text-meta text-ink-3">The same batches go into {t.to.name}.</p>
          <ReceiveTransfer transferId={t.id} locations={destination} />
        </Sheet>
      )}
    </>
  );
}

/** The transfer form's lists, with what's free per product per warehouse. */
const TRANSFER_FORM = `${referenceOf("products", "warehouses")} availability`;
type TransferFormData = { reference: Pick<Reference, "products" | "warehouses">; availability: Record<string, number> };

export async function NewTransferPage() {
  const { me, may } = await context();
  if (!may("transfers.create")) return <NoAccess what="transfers" />;
  const { reference: ref, availability: available } = await loadQuery<TransferFormData>(`query NewTransfer { ${TRANSFER_FORM} }`, {}, ["reference", "availability"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/transfers", label: "Transfers" }]} title="New transfer" />
      <TransferForm canAdd={canAddFrom(may)} org={me.org} reference={ref} available={available} />
    </>
  );
}

export async function EditTransferPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, may } = await context();
  if (!may("transfers.create")) return <NoAccess what="transfers" />;
  const { transfer: t, reference: ref, availability: available } = await loadQuery<TransferFormData & { transfer: Transfer }>(
    `query EditTransfer($id: String!) { transfer(id: $id) ${TRANSFER_FORM} }`,
    { id },
    ["transfer", "reference", "availability"],
  );
  return (
    <>
      <PageHeader crumbs={[{ href: "/transfers", label: "Transfers" }, { href: `/transfers/${t.id}`, label: t.number }]} title={`Edit ${t.number}`} />
      <TransferForm canAdd={canAddFrom(may)} org={me.org} reference={ref} transfer={t} available={available} />
    </>
  );
}
