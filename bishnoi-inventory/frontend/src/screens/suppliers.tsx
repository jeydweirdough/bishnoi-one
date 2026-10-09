import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { deleteSupplier, saveSupplier } from "../actions/inventory";
import { POStamp } from "../components/stamps";
import { RecordTools } from "../components/record-tools";
import { StepButton } from "../components/step-button";
import { SupplierForm } from "../components/supplier-form";
import { Chips, Figures, Filters, NoAccess, RowLink, Table, Td } from "../components/ui";
import { param, query } from "../lib/labels";
import { context, type Params, type Search } from "../lib/page";
import { given } from "../lib/reference";
import type { Supplier, SupplierRow } from "../lib/types";

const rate = (r: number | null | undefined) => (r == null ? "—" : `${Math.round(r * 100)}%`);

export async function SuppliersPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may } = await context();
  if (!may("suppliers.view")) return <NoAccess what="suppliers" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), state: param(s, "state") || "active" };
  const { suppliers } = await loadQuery<{ suppliers: SupplierRow[] }>(`query Suppliers($q: String, $state: String) { suppliers(q: $q, state: $state) }`, given(f), ["suppliers"]);
  return (
    <>
      <PageHeader
        title="Suppliers"
        actions={may("suppliers.create") && <LinkButton href="/suppliers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>Add supplier</LinkButton>}
      >
        Who you buy from: how to reach them, their terms, and how well they deliver.
      </PageHeader>
      <Chips label="Show" current={f.state} options={[{ value: "active", label: "Active", href: `/suppliers${query({ q: f.q })}` }, { value: "off", label: "Switched off", href: `/suppliers${query({ q: f.q, state: "off" })}` }, { value: "all", label: "All", href: `/suppliers${query({ q: f.q, state: "all" })}` }]} />
      <Filters q={f.q} placeholder="Name, code or contact" keep={{ state: f.state }} />
      <Sheet>
        {suppliers.length === 0 ? (
          <Empty icon="suppliers" title="No suppliers here" />
        ) : (
          <Table head={["Supplier", "Contact", "Terms", " Lead time", " Orders", " Fill rate", " On time", " Received"]} min="56rem">
            {suppliers.map((x) => (
              <tr key={x.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/suppliers/${x.id}`} sub={x.code}>{x.name}</RowLink></Td>
                <Td className="text-ink-2">{x.contactPerson ?? "—"}<span className="block text-meta text-ink-3">{x.phone ?? x.email ?? ""}</span></Td>
                <Td className="text-ink-2">{x.paymentTerms ?? "—"}</Td>
                <Td num>{x.leadTimeDays == null ? "—" : `${x.leadTimeDays} days`}</Td>
                <Td num>{x.performance?.orders ?? 0}</Td>
                <Td num>{rate(x.performance?.fillRate)}</Td>
                <Td num>{rate(x.performance?.onTimeRate)}</Td>
                <Td num>{fmt.pesoCompact(x.performance?.spend ?? 0)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function SupplierPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, day } = await context();
  if (!may("suppliers.view")) return <NoAccess what="suppliers" />;
  const { supplier: x } = await loadQuery<{ supplier: Supplier }>(`query Supplier($id: String!) { supplier(id: $id) }`, { id }, ["supplier"]);
  const perf = x.performance;
  return (
    <>
      <PageHeader
        crumbs={[{ href: "/suppliers", label: "Suppliers" }]}
        title={x.name}
        tools={
          <RecordTools
            what="supplier"
            name={x.name}
            editHref={may("suppliers.edit") ? `/suppliers/${x.id}/edit` : undefined}
            remove={may("suppliers.delete") ? deleteSupplier.bind(null, x.id) : undefined}
            after="/suppliers"
            removeNote="A supplier with purchase orders can't be deleted; switch it off instead, at the foot of its Edit page."
          />
        }
        actions={may("purchasing.create") && x.isActive && <LinkButton href={`/purchase-orders/new?supplier=${x.id}`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>New purchase order</LinkButton>}
      >
        <span className="font-mono text-meta">{x.code}</span>
        {!x.isActive && <> · <strong>Switched off</strong></>}
      </PageHeader>
      <Figures
        items={[
          { label: "Purchase orders", value: perf?.orders ?? 0 },
          { label: "Units received / ordered", value: `${fmt.count(perf?.received ?? 0)} / ${fmt.count(perf?.ordered ?? 0)}` },
          { label: "Fill rate", value: rate(perf?.fillRate) },
          { label: "Delivered on time", value: rate(perf?.onTimeRate) },
          { label: "Average lead time", value: perf?.averageLeadDays == null ? "—" : `${perf.averageLeadDays} days` },
          { label: "Received value", value: fmt.peso(perf?.spend ?? 0) },
        ]}
      />
      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-5">
          <Sheet>
            <div className="px-5 pt-4"><SectionTitle icon="purchaseOrders">Purchase history</SectionTitle></div>
            {x.orders.length === 0 ? (
              <p className="px-5 pb-4 text-meta text-ink-3">No purchase orders yet.</p>
            ) : (
              <Table head={["Order", "Status", "Ordered", "Expected", " Received", " Total"]}>
                {x.orders.map((po) => (
                  <tr key={po.id} className="relative hover:bg-bench/40">
                    <Td><RowLink href={`/purchase-orders/${po.id}`}>{po.number}</RowLink></Td>
                    <Td><POStamp status={po.status} late={po.late} /></Td>
                    <Td>{day(po.orderedOn)}</Td>
                    <Td>{day(po.expectedOn)}</Td>
                    <Td num>{fmt.count(po.received)} / {fmt.count(po.ordered)}</Td>
                    <Td num>{fmt.peso(po.total)}</Td>
                  </tr>
                ))}
              </Table>
            )}
          </Sheet>
          <Sheet>
            <div className="px-5 pt-4"><SectionTitle icon="pricing">What they charge</SectionTitle></div>
            {x.prices.length === 0 ? (
              <p className="px-5 pb-4 text-meta text-ink-3">No prices yet. They&apos;re recorded when an order is placed, or on a product&apos;s page.</p>
            ) : (
              <Table head={["Product", "Their code", " Lead time", " Price", "Updated"]}>
                {x.prices.map((p) => (
                  <tr key={p.product.id} className="relative hover:bg-bench/40">
                    <Td><RowLink href={`/products/${p.product.id}`} sub={p.product.sku}>{p.product.name}</RowLink></Td>
                    <Td>{p.supplierSku ?? "—"}</Td>
                    <Td num>{p.leadTimeDays == null ? "—" : `${p.leadTimeDays} days`}</Td>
                    <Td num>{fmt.peso(p.price)}</Td>
                    <Td className="text-meta text-ink-3">{fmt.whenLabel(p.updatedAt)}</Td>
                  </tr>
                ))}
              </Table>
            )}
          </Sheet>
        </div>
        <div className="space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="particulars">Details</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  ["Contact", x.contactPerson],
                  ["Email", x.email ? <a href={`mailto:${x.email}`} className="hover:text-hema hover:underline">{x.email}</a> : null],
                  ["Phone", x.phone],
                  ["Address", x.address],
                  ["Payment terms", x.paymentTerms],
                  ["Lead time", x.leadTimeDays == null ? null : `${x.leadTimeDays} days`],
                ]}
              />
            </div>
            {x.contacts.length > 0 && (
              <ul className="mt-4 space-y-2 border-t border-rule pt-3 text-sm">
                {x.contacts.map((c, i) => (
                  <li key={i}>
                    <span className="font-semibold">{c.name}</span>
                    {c.role && <span className="text-ink-2"> · {c.role}</span>}
                    <span className="block text-meta text-ink-3">{[c.email, c.phone].filter(Boolean).join(" · ")}</span>
                  </li>
                ))}
              </ul>
            )}
            {x.notes && <p className="mt-4 text-sm whitespace-pre-line text-ink-2">{x.notes}</p>}
          </Sheet>
          {x.products.length > 0 && (
            <Sheet className="px-5 pt-4 pb-4">
              <SectionTitle icon="products">Usually bought from them</SectionTitle>
              <ul className="mt-2 space-y-1 text-sm">
                {x.products.map((p) => <li key={p.id}><Link href={`/products/${p.id}`} className="hover:text-hema hover:underline">{p.name}</Link></li>)}
              </ul>
            </Sheet>
          )}
        </div>
      </div>
    </>
  );
}

export async function NewSupplierPage() {
  const { may } = await context();
  if (!may("suppliers.create")) return <NoAccess what="adding suppliers" />;
  return (
    <>
      <PageHeader crumbs={[{ href: "/suppliers", label: "Suppliers" }]} title="Add a supplier" />
      <SupplierForm />
    </>
  );
}

export async function EditSupplierPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { may } = await context();
  if (!may("suppliers.edit")) return <NoAccess what="changing suppliers" />;
  const { supplier: x } = await loadQuery<{ supplier: Supplier }>(`query Supplier($id: String!) { supplier(id: $id) }`, { id }, ["supplier"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/suppliers", label: "Suppliers" }, { href: `/suppliers/${x.id}`, label: x.name }]} title={`Edit ${x.name}`} />
      <SupplierForm supplier={x} />
      <SupplierActive supplier={x} />
    </>
  );
}


function SupplierActive({ supplier }: { supplier: Supplier }) {
  return (
    <div className="mt-8 border-t border-rule pt-4">
      <StepButton
        run={saveSupplier.bind(null, supplier.id, { isActive: !supplier.isActive })}
        label={supplier.isActive ? "Switch this supplier off" : "Switch this supplier back on"}
        done={supplier.isActive ? "Supplier switched off" : "Supplier switched on"}
        variant="quiet"
      />
    </div>
  );
}
