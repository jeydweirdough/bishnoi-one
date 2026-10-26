import { FirstStep } from "@/src/modules/inventory/components/setup";
import { ExternalLink, Pencil, Plus, ShoppingCart, Trash2 } from "lucide-react";
import { RowMenu } from "@/src/platform/ui/row-menu";
import Link from "next/link";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { deleteSupplier, saveSupplier } from "@/src/modules/inventory/actions/inventory";
import { POStamp } from "@/src/modules/inventory/components/stamps";
import { RecordTools } from "@/src/modules/inventory/components/record-tools";
import { StepButton } from "@/src/modules/inventory/components/step-button";
import { SupplierForm } from "@/src/modules/inventory/components/supplier-form";
import { Chips, Figures, Filters, NoAccess, RowLink, Table, Td } from "@/src/modules/inventory/components/ui";
import { BarList, DetailPanel, InfoCard, InfoSection, StatCards } from "@/src/modules/inventory/components/detail";
import { param, query } from "@/src/modules/inventory/lib/labels";
import { Pager } from "@/src/modules/inventory/platform/ui/pager";
import { context, keepInRange, paging, type Params, type Search } from "@/src/modules/inventory/lib/page";
import { given } from "@/src/modules/inventory/lib/reference";
import type { Paged, Supplier, SupplierRow } from "@/src/modules/inventory/lib/types";

const rate = (r: number | null | undefined) => (r == null ? "—" : `${Math.round(r * 100)}%`);

export async function SuppliersPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may } = await context();
  if (!may("suppliers.view")) return <NoAccess what="suppliers" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), state: param(s, "state") || "active" };
  const { page, size, vars } = paging(s);
  const base = `/inventory/suppliers${query({ q: f.q, state: f.state === "active" ? "" : f.state })}`;
  const { suppliers: list } = await loadQuery<{ suppliers: Paged<SupplierRow> }>(
    `query Suppliers($q: String, $state: String, $limit: Int, $offset: Int) { suppliers(q: $q, state: $state, limit: $limit, offset: $offset) }`,
    { ...given(f), ...vars },
    ["suppliers"],
  );
  keepInRange(list.items.length, list.total, page, base);
  const suppliers = list.items;
  return (
    <>
      <PageHeader
        title="Vendors"
        actions={may("suppliers.create") && <LinkButton href="/inventory/suppliers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>Add supplier</LinkButton>}
      >
        Vendors you buy from, with contact details, payment terms and delivery performance.
      </PageHeader>
      <Chips label="Status" current={f.state} options={[{ value: "active", label: "Active", href: `/inventory/suppliers${query({ q: f.q })}` }, { value: "off", label: "Inactive", href: `/inventory/suppliers${query({ q: f.q, state: "off" })}` }, { value: "all", label: "All", href: `/inventory/suppliers${query({ q: f.q, state: "all" })}` }]} />
      <Filters q={f.q} placeholder="Name, code or contact" keep={{ state: f.state }} />
      <Sheet>
        {suppliers.length === 0 ? (
          <FirstStep icon="suppliers" title="No vendors" body="Vendors you buy from, with their payment terms and lead times." href="/inventory/suppliers/new" action="Add supplier" permission="suppliers.create" filtered={Boolean(f.q || f.state !== "active")} clear="/inventory/suppliers" may={may} />
        ) : (
          <Table head={["Supplier", "Contact", "Payment terms", " Lead time", " Orders", " Fill rate", " On-time delivery", " Received", <span key="a" className="sr-only">Actions</span>]} min="56rem">
            {suppliers.map((x) => (
              <tr key={x.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/inventory/suppliers/${x.id}`} sub={x.code}>{x.name}</RowLink></Td>
                <Td className="text-ink-2">{x.contactPerson ?? "—"}<span className="block text-meta text-ink-3">{x.phone ?? x.email ?? ""}</span></Td>
                <Td className="text-ink-2">{x.paymentTerms ?? "—"}</Td>
                <Td num>{x.leadTimeDays == null ? "—" : `${x.leadTimeDays} days`}</Td>
                <Td num>{x.performance?.orders ?? 0}</Td>
                <Td num>{rate(x.performance?.fillRate)}</Td>
                <Td num>{rate(x.performance?.onTimeRate)}</Td>
                <Td num>{fmt.pesoCompact(x.performance?.spend ?? 0)}</Td>
                <td className="px-2 py-2 text-right">
                  <RowMenu
                    label={`Actions for ${x.name}`}
                    items={[
                      { label: "Open", icon: <ExternalLink />, href: `/inventory/suppliers/${x.id}` },
                      ...(may("suppliers.edit") ? [{ label: "Edit", icon: <Pencil />, href: `/inventory/suppliers/${x.id}/edit` }] : []),
                      "divider" as const,
                      ...(may("purchasing.create") && x.isActive ? [{ label: "New purchase order", icon: <ShoppingCart />, href: `/inventory/purchase-orders/new?supplier=${x.id}` }] : []),
                      ...(may("suppliers.delete")
                        ? [
                            "divider" as const,
                            { label: "Delete", icon: <Trash2 />, run: deleteSupplier.bind(null, x.id), danger: true, confirm: `Delete ${x.name}? A supplier with purchase orders cannot be deleted; deactivate it instead.`, done: `${x.name} deleted` },
                          ]
                        : []),
                    ]}
                  />
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
      <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "supplier" : "suppliers"} />
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
        crumbs={[{ href: "/inventory/suppliers", label: "Vendors" }]}
        title={x.name}
        tools={
          <RecordTools
            what="supplier"
            name={x.name}
            editHref={may("suppliers.edit") ? `/inventory/suppliers/${x.id}/edit` : undefined}
            remove={may("suppliers.delete") ? deleteSupplier.bind(null, x.id) : undefined}
            after="/inventory/suppliers"
            removeNote="A supplier with purchase orders cannot be deleted. Deactivate it instead from its Edit page."
          />
        }
        actions={may("purchasing.create") && x.isActive && <LinkButton href={`/inventory/purchase-orders/new?supplier=${x.id}`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>New purchase order</LinkButton>}
      >
        <span className="font-mono text-meta">{x.code}</span>
        {!x.isActive && <> · <strong>Inactive</strong></>}
      </PageHeader>
      <DetailPanel>
        <StatCards
          items={[
            { label: "Purchase orders", value: fmt.count(perf?.orders ?? 0), note: `${fmt.peso(perf?.spend ?? 0)} received` },
            { label: "Fill rate", value: rate(perf?.fillRate), note: `${fmt.count(perf?.received ?? 0)} of ${fmt.count(perf?.ordered ?? 0)} units` },
            { label: "On-time delivery", value: rate(perf?.onTimeRate), flag: perf?.onTimeRate != null && perf.onTimeRate < 0.8, note: perf?.late ? `${fmt.count(perf.late)} late` : undefined },
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
              ["Status", x.isActive ? "Active" : "Inactive"],
              ["Created", fmt.whenLabel(x.createdAt)],
            ]}
          />
          {x.contacts.length > 0 && (
            <InfoSection icon="people" title="Other contacts" items={x.contacts.map((c) => [c.role ? `${c.name} · ${c.role}` : c.name, [c.email, c.phone].filter(Boolean).join(" · ") || null] as [string, string | null])} />
          )}
        </InfoCard>
        <BarList
          title="Products supplied"
          icon="products"
          rows={x.prices.map((p) => ({
            key: p.product.id,
            href: `/inventory/products/${p.product.id}`,
            name: p.product.name,
            sub: [p.product.sku, p.supplierSku && `supplier code ${p.supplierSku}`, p.leadTimeDays != null && `${p.leadTimeDays} days`].filter(Boolean).join(" · "),
            pill: <span className="text-sm font-semibold text-ink tabular-nums">{fmt.peso(p.price)}</span>,
            share: p.price / Math.max(1, ...x.prices.map((q) => q.price)),
          }))}
          empty="No supplier prices. Prices are recorded when an order is placed, or on the product page."
        />
      </DetailPanel>

      <Sheet className="mt-5">
        <div className="px-5 pt-4"><SectionTitle icon="purchaseOrders">Purchase history</SectionTitle></div>
        {x.orders.length === 0 ? (
          <p className="px-5 pb-4 text-meta text-ink-3">No purchase orders.</p>
        ) : (
          <Table head={["Order", "Status", "Ordered", "Expected", " Received", " Total"]}>
            {x.orders.map((po) => (
              <tr key={po.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/inventory/purchase-orders/${po.id}`}>{po.number}</RowLink></Td>
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
      <PageHeader crumbs={[{ href: "/inventory/suppliers", label: "Vendors" }]} title="New vendor" />
      <SupplierForm />
    </>
  );
}

export async function EditSupplierPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { may } = await context();
  if (!may("suppliers.edit")) return <NoAccess what="editing suppliers" />;
  const { supplier: x } = await loadQuery<{ supplier: Supplier }>(`query Supplier($id: String!) { supplier(id: $id) }`, { id }, ["supplier"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/suppliers", label: "Vendors" }, { href: `/inventory/suppliers/${x.id}`, label: x.name }]} title={`Edit ${x.name}`} />
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
        label={supplier.isActive ? "Deactivate supplier" : "Activate supplier"}
        done={supplier.isActive ? "Supplier deactivated" : "Supplier activated"}
        variant="quiet"
      />
    </div>
  );
}
