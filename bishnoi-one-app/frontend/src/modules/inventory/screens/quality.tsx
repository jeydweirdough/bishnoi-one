import Link from "next/link";
import { load } from "@/src/modules/inventory/platform/lib/api";
import { NoAccess, Table, Td } from "@/src/modules/inventory/components/ui";
import { QualityCheckForm } from "@/src/modules/inventory/components/quality";
import { context, type Params, type Search } from "@/src/modules/inventory/lib/page";
import type { QualityCheck, QualityCheckBrief } from "@/src/modules/inventory/lib/types";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";

// Quality checks on receipt (feature plan step 14a): receive → check → store.

const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export async function QualityChecksPage({ searchParams }: { searchParams: Search }) {
  const { may, at } = await context();
  if (!may("receiving.view")) return <NoAccess what="quality checks" />;
  const status = one((await searchParams).status);
  const { items, waiting } = await load<{ items: QualityCheckBrief[]; waiting: number }>(`/inventory/quality-checks${status ? `?status=${status}` : ""}`);
  return (
    <>
      <PageHeader
        title="Quality checks"
        tools={<ToggleLinks current={status} options={[{ value: "", label: "All", href: "/inventory/quality-checks" }, { value: "waiting", label: `Waiting (${waiting})`, href: "/inventory/quality-checks?status=waiting" }, { value: "done", label: "Done", href: "/inventory/quality-checks?status=done" }]} />}
      >
        Goods received into a warehouse that checks on arrival wait here, on hold, until checked. What passes can be used; what fails is set aside as damaged.
      </PageHeader>
      <Sheet>
        {items.length === 0 ? (
          <Empty icon="approvals" title={status === "waiting" ? "Nothing waiting" : "No quality checks yet"}
            source="Purchase receives into a warehouse that checks goods on arrival (Warehouses → Check goods on arrival)." />
        ) : (
          <Table head={["Check", "Receipt", "Vendor", "Warehouse", "Received", " Units", " Passed", " Failed"]} min="52rem">
            {items.map((c) => (
              <tr key={c.id} className="relative hover:bg-bench/40">
                <Td>
                  <Link href={`/inventory/quality-checks/${c.id}`} className="font-semibold text-ink hover:underline after:absolute after:inset-0">{c.number}</Link>
                  <span className="block text-meta text-ink-3">{c.status === "waiting" ? "Waiting" : `Done ${at(c.checkedAt)}`}</span>
                </Td>
                <Td>{c.receipt.number}</Td>
                <Td>{c.supplier?.name ?? "—"}</Td>
                <Td>{c.warehouse.name}</Td>
                <Td>{at(c.receivedAt)}</Td>
                <Td num>{c.units}</Td>
                <Td num>{c.status === "done" ? c.passed : "—"}</Td>
                <Td num className={c.failed ? "font-semibold text-danger" : undefined}>{c.status === "done" ? c.failed : "—"}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function QualityCheckPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { may, at, day } = await context();
  if (!may("receiving.view")) return <NoAccess what="quality checks" />;
  const c = await load<QualityCheck>(`/inventory/quality-checks/${encodeURIComponent(id)}`);
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/quality-checks", label: "Quality checks" }]} title={c.number}>
        {c.status === "waiting" ? "Waiting" : `Done ${at(c.checkedAt)} by ${c.checkedBy?.name ?? "—"}`} · receipt{" "}
        <Link href={`/inventory/receipts/${c.receipt.id}`} className="text-ink hover:underline">{c.receipt.number}</Link>
        {c.supplier && <> from {c.supplier.name}</>} into {c.warehouse.name}, received {at(c.receivedAt)}
      </PageHeader>
      <Sheet className="px-5 py-4">
        {c.status === "waiting" && may("receiving.receive") ? (
          <QualityCheckForm check={c} />
        ) : (
          <Table head={["Product", "Batch", " Received", " Passed", " Failed", "Why", "Note"]} min="48rem">
            {c.lines.map((l) => (
              <tr key={l.id}>
                <Td><span className="font-medium">{l.product.name}</span><span className="block text-meta text-ink-3">{l.product.sku} · {l.location.code}</span></Td>
                <Td>{l.batch ? <>{l.batch.batchNo}{l.batch.expiresOn && <span className="block text-meta text-ink-3">exp. {day(l.batch.expiresOn)}</span>}</> : "—"}</Td>
                <Td num>{l.quantity}</Td>
                <Td num>{l.passed ?? "—"}</Td>
                <Td num className={l.failed ? "font-semibold text-danger" : undefined}>{l.failed ?? "—"}</Td>
                <Td>{l.reasonLabel ?? "—"}</Td>
                <Td>{l.note ?? ""}</Td>
              </tr>
            ))}
          </Table>
        )}
        {c.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{c.notes}</p>}
      </Sheet>
    </>
  );
}
