import { ArrowRight, Ban, ExternalLink, Pencil, Plus, Printer, Trash2 } from "lucide-react";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { ToggleLinks } from "@/src/modules/inventory/platform/ui/toggle-links";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { deleteTransfer, transferStep } from "@/src/modules/inventory/actions/inventory";
import { TransferForm } from "@/src/modules/inventory/components/document-forms";
import { PrintLink } from "@/src/modules/inventory/components/print-button";
import { PickForm, type PickLine } from "@/src/modules/inventory/components/pick-form";
import { ReceiveTransfer } from "@/src/modules/inventory/components/receive-transfer";
import { RecordTools } from "@/src/modules/inventory/components/record-tools";
import { TransferStamp } from "@/src/modules/inventory/components/stamps";
import { StepButton } from "@/src/modules/inventory/components/step-button";
import { Chips, Filters, NoAccess, RowLink, Table, Td, Trail } from "@/src/modules/inventory/components/ui";
import { param, query } from "@/src/modules/inventory/lib/labels";
import { FirstStep, NeedsFirst } from "@/src/modules/inventory/components/setup";
import { loadSetup } from "@/src/modules/inventory/lib/setup";
import { TransfersBoard } from "@/src/modules/inventory/screens/boards";
import { Pager } from "@/src/modules/inventory/platform/ui/pager";
import { canAddFrom, context, keepInRange, paging, type Params, type Search } from "@/src/modules/inventory/lib/page";
import { batchChoices, given, referenceOf } from "@/src/modules/inventory/lib/reference";
import type { BatchRow, Paged, Reference, Transfer, TransferBrief } from "@/src/modules/inventory/lib/types";

export async function TransfersPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, at, day } = await context();
  if (!may("transfers.view")) return <NoAccess what="transfers" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), status: param(s, "status") };
  const board = param(s, "view") !== "list" && !f.status;
  // The board shows every open one in its columns; the list is read a page at a time.
  const { page, size, vars } = paging(s);
  const base = `/inventory/transfers${query({ ...f, view: board ? "" : "list" })}`;
  const { transfers: got } = await loadQuery<{ transfers: TransferBrief[] | Paged<TransferBrief> }>(
    `query Transfers($q: String, $status: String, $limit: Int, $offset: Int) { transfers(q: $q, status: $status, limit: $limit, offset: $offset) }`,
    { ...given(f), ...(board ? {} : vars) },
    ["transfers"],
  );
  const list: Paged<TransferBrief> = Array.isArray(got) ? { items: got, total: got.length } : got;
  if (!board) keepInRange(list.items.length, list.total, page, base);
  const transfers = list.items;
  const chip = (status: string, label: string) => ({ value: status, label, href: `/inventory/transfers${query({ q: f.q, status })}` });
  return (
    <>
      <PageHeader
        title="Transfer orders"
        actions={may("transfers.create") && <LinkButton href="/inventory/transfers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New transfer</LinkButton>}
      >
        Moving stock between warehouses: requested, approved, dispatched, in transit, received.
      </PageHeader>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <ToggleLinks
          current={board ? "board" : "list"}
          options={[
            { value: "board", label: "Board", href: `/inventory/transfers${query({ ...f, status: "", view: "" })}` },
            { value: "list", label: "List", href: `/inventory/transfers${query({ ...f, view: "list" })}` },
            { value: "map", label: "Map", href: "/inventory/transfers/map" },
          ]}
        />
      </div>
      {!board && <Chips label="Status" current={f.status} options={[chip("", "All"), chip("draft", "Drafts"), chip("requested", "Requested"), chip("approved", "Approved"), chip("in_transit", "In transit"), chip("received", "Received"), chip("cancelled", "Cancelled")]} />}
      <Filters q={f.q} placeholder="Transfer number" keep={{ status: f.status, view: board ? "" : "list" }} />
      {board && transfers.length > 0 ? (
        <TransfersBoard transfers={transfers} fmt={fmt} day={day} may={may} />
      ) : (
      <Sheet>
        {transfers.length === 0 ? (
          <FirstStep icon="transfers" title="No transfer orders" body="Move stock between warehouses, with approval and in-transit tracking." needs={["twoWarehouses", "stock"]} href="/inventory/transfers/new" action="New transfer" permission="transfers.create" filtered={Boolean(f.q || f.status)} clear="/inventory/transfers" may={may} />
        ) : (
          <Table head={["Transfer", "From → to", "Status", "Requested", "Dispatched", "Received", " Units", <span key="a" className="sr-only">Actions</span>]} min="52rem">
            {transfers.map((t) => (
              <tr key={t.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/inventory/transfers/${t.id}`} sub={`${t.lineCount} line${t.lineCount === 1 ? "" : "s"}`}>{t.number}</RowLink></Td>
                <Td className="whitespace-nowrap">{t.from.code} <ArrowRight className="inline size-3.5 text-ink-3" aria-label="to" /> {t.to.code}</Td>
                <Td><TransferStamp status={t.status} /></Td>
                <Td className="text-meta text-ink-2">{at(t.requestedAt)}</Td>
                <Td className="text-meta text-ink-2">{at(t.dispatchedAt)}</Td>
                <Td className="text-meta text-ink-2">{at(t.receivedAt)}</Td>
                <Td num>{fmt.count(t.units)}</Td>
                <td className="px-2 py-2 text-right">
                  <RowMenu
                    label={`Actions for ${t.number}`}
                    items={[
                      { label: "Open", icon: <ExternalLink />, href: `/inventory/transfers/${t.id}` },
                      ...((t.status === "draft" || t.status === "requested") && may("transfers.create") ? [{ label: "Edit", icon: <Pencil />, href: `/inventory/transfers/${t.id}/edit` }] : []),
                      "divider" as const,
                      { label: "Print", icon: <Printer />, href: `/inventory/print/transfers/${t.id}` },
                      ...(((t.status === "draft" || t.status === "requested") ? may("transfers.create") : t.status === "approved" && may("transfers.approve"))
                        ? [
                            "divider" as const,
                            { label: "Cancel transfer", icon: <Ban />, run: transferStep.bind(null, t.id, "cancel" as const), danger: true, confirm: `Cancel ${t.number}?`, done: "Transfer cancelled" },
                          ]
                        : []),
                      ...(t.status === "draft" && may("transfers.create")
                        ? [{ label: "Delete", icon: <Trash2 />, run: deleteTransfer.bind(null, t.id), danger: true, confirm: `Delete ${t.number}? This can't be undone.`, done: `${t.number} deleted` }]
                        : []),
                    ]}
                  />
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
      )}
      {!board && <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "transfer" : "transfers"} />}
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
        crumbs={[{ href: "/inventory/transfers", label: "Transfer orders" }]}
        title={t.number}
        tools={pending && (
          <RecordTools what="transfer" name={t.number} editHref={may("transfers.create") ? `/inventory/transfers/${t.id}/edit` : undefined} remove={t.status === "draft" && may("transfers.create") ? deleteTransfer.bind(null, t.id) : undefined} after="/inventory/transfers" />
        )}
        actions={
          <>
            <PrintLink href={`/inventory/print/transfers/${t.id}`} />
            {t.status === "draft" && may("transfers.create") && <StepButton run={transferStep.bind(null, t.id, "request")} label="Submit request" done="Transfer requested" />}
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
        <Table head={["Product", " Quantity", ...(pending || t.status === "approved" ? [` Available in ${t.from.code}`] : ["Batches dispatched"])]}>
          {t.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/inventory/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
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
        <Sheet className="mt-6 scroll-mt-6 px-5 pt-4 pb-5" id="dispatch">
          <SectionTitle icon="transfers">Dispatch</SectionTitle>
          <p className="mb-3 text-meta text-ink-3">Stock leaves {t.from.name} and stays in transit until received at {t.to.name}.</p>
          <PickForm kind="transfer" documentId={t.id} lines={pickLines} label="Dispatch" />
        </Sheet>
      )}
      {t.status === "in_transit" && may("transfers.receive") && (
        <Sheet className="mt-6 scroll-mt-6 px-5 pt-4 pb-5" id="receive">
          <SectionTitle icon="receiving">Receive transfer</SectionTitle>
          <p className="mb-3 text-meta text-ink-3">The dispatched batches are received into {t.to.name}.</p>
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
  // What this page needs first; if any is missing, that instead of a form that can't be finished.
  const gate = NeedsFirst({ setup: await loadSetup(), needs: ["twoWarehouses", "stock"], then: "/inventory/transfers/new", title: "New transfer", doing: "move stock between warehouses", crumbs: [{ href: "/inventory/transfers", label: "Transfer orders" }], may });
  if (gate) return gate;
  const { reference: ref, availability: available } = await loadQuery<TransferFormData>(`query NewTransfer { ${TRANSFER_FORM} }`, {}, ["reference", "availability"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/transfers", label: "Transfer orders" }]} title="New transfer order" />
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
      <PageHeader crumbs={[{ href: "/inventory/transfers", label: "Transfer orders" }, { href: `/inventory/transfers/${t.id}`, label: t.number }]} title={`Edit ${t.number}`} />
      <TransferForm canAdd={canAddFrom(may)} org={me.org} reference={ref} transfer={t} available={available} />
    </>
  );
}
