import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { enc, load } from "@/src/platform/lib/api";
import { BatchStatusMark, Head, NoAccess, SearchBar } from "../components/bits";
import { DeleteRecord } from "../components/delete-record";
import { SupplierForm } from "../components/supplier-form";
import { pageFor, param, type Search } from "../lib/page";
import type { Supplier, SupplierDetail } from "../lib/types";

export const metadata = { title: "Suppliers" };

export default async function SuppliersPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("suppliers.view");
  if (!allowed) return <NoAccess what="suppliers" />;
  const search = await searchParams;
  const q = param(search, "q");
  const state = param(search, "state") === "off" ? "off" : "active";
  const rows = await load<Supplier[]>(`/suppliers?state=${state}${q ? `&q=${enc(q)}` : ""}`);

  return (
    <>
      <PageHeader
        title="Suppliers"
        actions={
          may("suppliers.create") && (
            <LinkButton href="/suppliers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add supplier
            </LinkButton>
          )
        }
      >
        Who the pharmacy buys from. Deliveries are taken in under Stock → Receiving.
      </PageHeader>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <SearchBar q={q} placeholder="Name or contact" keep={{ state }} />
        <ToggleLinks
          current={state}
          options={[
            { value: "active", label: "Active", href: `/suppliers${q ? `?q=${enc(q)}` : ""}` },
            { value: "off", label: "Switched off", href: `/suppliers?state=off${q ? `&q=${enc(q)}` : ""}` },
          ]}
        />
      </div>
      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="suppliers" title={q ? "No suppliers match" : state === "off" ? "Nobody switched off" : "No suppliers yet"} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <Head columns={["Supplier", "Contact", { label: "Deliveries", right: true }, { label: "Last delivery", right: true }]} />
              <tbody className="divide-y divide-rule">
                {rows.map((s) => (
                  <tr key={s.id} className="relative hover:bg-bench/40">
                    <td className="py-3 pr-3 pl-5">
                      <Link href={`/suppliers/${s.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                        {s.name}
                      </Link>
                    </td>
                    <td className="px-3 py-3 text-ink-2">
                      {s.contactPerson ?? "—"}
                      {(s.phone || s.email) && <span className="block text-meta text-ink-3">{[s.phone, s.email].filter(Boolean).join(" · ")}</span>}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">{s.deliveryCount}</td>
                    <td className="py-3 pr-5 pl-3 text-right text-meta text-ink-2">{s.lastDeliveryOn ? fmt.dateLabel(s.lastDeliveryOn) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </>
  );
}

export async function SupplierPage({ params }: { params: Promise<{ id: string }> }) {
  const { fmt, allowed, may } = await pageFor("suppliers.view");
  if (!allowed) return <NoAccess what="suppliers" />;
  const { id } = await params;
  const s = await load<SupplierDetail>(`/suppliers/${enc(id)}`);
  return (
    <>
      <PageHeader
        crumbs={[{ href: "/suppliers", label: "Suppliers" }]}
        title={s.name}
        tools={
          may("suppliers.delete") && (
            <DeleteRecord what="supplier" name={s.name} kind="supplier" id={s.id} after="/suppliers" body="Only a supplier with no deliveries on record can be deleted. Switch them off instead." />
          )
        }
      >
        {s.isActive ? "Active" : "Switched off"} · {s.deliveryCount} deliver{s.deliveryCount === 1 ? "y" : "ies"} on record
      </PageHeader>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <Sheet className="px-5 py-6 sm:px-8">
          <SupplierForm key={s.updatedAt} supplier={s} canEdit={may("suppliers.edit")} />
        </Sheet>
        <div className="space-y-4">
          <Sheet>
            <div className="px-5 pt-5">
              <SectionTitle icon="receive">Deliveries</SectionTitle>
            </div>
            {s.deliveries.length === 0 ? (
              <p className="px-5 py-4 text-meta text-ink-3">None yet.</p>
            ) : (
              <ul className="mt-3 divide-y divide-rule border-t border-rule">
                {s.deliveries.map((d) => (
                  <li key={d.id} className="flex justify-between gap-3 px-5 py-2.5 text-sm">
                    <Link href={`/stock/receivings/${d.id}`} className="font-semibold text-hema hover:underline">
                      {d.number}
                    </Link>
                    <span className="text-meta text-ink-2">
                      {d.reference ? `${d.reference} · ` : ""}
                      {fmt.dateLabel(d.receivedOn)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
          <Sheet>
            <div className="px-5 pt-5">
              <SectionTitle icon="batches">Their batches on the shelf</SectionTitle>
            </div>
            {s.batches.length === 0 ? (
              <p className="px-5 py-4 text-meta text-ink-3">None on hand.</p>
            ) : (
              <ul className="mt-3 divide-y divide-rule border-t border-rule">
                {s.batches.map((b) => (
                  <li key={b.id} className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm">
                    <span className="min-w-0">
                      <span className="block truncate">{b.medicine}</span>
                      <span className="block text-meta text-ink-3">
                        Lot {b.lotNo} · expires {fmt.dateLabel(b.expiresOn)}
                      </span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-1 tabular-nums">
                      {b.qtyOnHand}
                      {b.status !== "available" && <BatchStatusMark status={b.status} />}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        </div>
      </div>
    </>
  );
}

export async function SupplierNewPage() {
  const { allowed } = await pageFor("suppliers.create");
  if (!allowed) return <NoAccess what="adding suppliers" />;
  return (
    <>
      <PageHeader crumbs={[{ href: "/suppliers", label: "Suppliers" }]} title="Add supplier" />
      <Sheet className="max-w-[50rem] px-5 py-6 sm:px-8">
        <SupplierForm />
      </Sheet>
    </>
  );
}
