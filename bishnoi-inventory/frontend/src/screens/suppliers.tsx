import { FirstStep } from "../components/setup";
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
import { BarList, DetailPanel, InfoCard, InfoSection, StatCards } from "../components/detail";
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
          <FirstStep icon="suppliers" title="No suppliers yet" body="Who you buy from, with their terms and lead time." href="/suppliers/new" action="Add supplier" permission="suppliers.create" filtered={Boolean(f.q || f.state !== "active")} clear="/suppliers" may={may} />
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
      <DetailPanel>
        <StatCards
          items={[
            { label: "Purchase orders", value: fmt.count(perf?.orders ?? 0), note: `${fmt.peso(perf?.spend ?? 0)} received` },
            { label: "Fill rate", value: rate(perf?.fillRate), note: `${fmt.count(perf?.received ?? 0)} of ${fmt.count(perf?.ordered ?? 0)} units` },
            { label: "Delivered on time", value: rate(perf?.onTimeRate), flag: perf?.onTimeRate != null && perf.onTimeRate < 0.8, note: perf?.late ? `${fmt.count(perf.late)} late` : undefined },
          ]}
        />
        <InfoCard>
          <InfoSection
            icon="info"
            title="Basic information"
            items={[
              ["Supplier name", x.name],
              ["Code", <span key="code" className="font-mono">{x.code}</span>],
              ["Contact", x.contactPerson],
              ["Phone", x.phone],
              ["Email", x.email ? <a key="email" href={`mailto:${x.email}`} className="hover:text-ink hover:underline">{x.email}</a> : null],
              ["Address", x.address],
            ]}
          >
            {x.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{x.notes}</p>}
          </InfoSection>
          <InfoSection
            icon="purchaseOrders"
            title="Purchasing"
            items={[
              ["Payment terms", x.paymentTerms],
              ["Lead time", x.leadTimeDays == null ? null : `${x.leadTimeDays} days`],
              ["Average lead time", perf?.averageLeadDays == null ? null : `${perf.averageLeadDays} days`],
              ["Received value", fmt.peso(perf?.spend ?? 0)],
              ["Status", x.isActive ? "Active" : "Switched off"],
              ["Since", fmt.whenLabel(x.createdAt)],
            ]}
          />
          {x.contacts.length > 0 && (
            <InfoSection icon="people" title="Other contacts" items={x.contacts.map((c) => [c.role ? `${c.name} · ${c.role}` : c.name, [c.email, c.phone].filter(Boolean).join(" · ") || null] as [string, string | null])} />
          )}
        </InfoCard>
        <BarList
          title="What they supply"
          icon="products"
          rows={x.prices.map((p) => ({
            key: p.product.id,
            href: `/products/${p.product.id}`,
            name: p.product.name,
            sub: [p.product.sku, p.supplierSku && `their code ${p.supplierSku}`, p.leadTimeDays != null && `${p.leadTimeDays} days`].filter(Boolean).join(" · "),
            pill: <span className="text-sm font-semibold text-ink tabular-nums">{fmt.peso(p.price)}</span>,
            share: p.price / Math.max(1, ...x.prices.map((q) => q.price)),
          }))}
          empty="No prices yet. They're recorded when an order is placed, or on a product's page."
        />
      </DetailPanel>

      <Sheet className="mt-5">
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
