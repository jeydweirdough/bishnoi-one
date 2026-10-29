"use client";

import { Checkbox } from "antd";
import { FileText, Trash2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { deleteProductDocument, dropshipDelivered, saveProductDocument, sendSaleDocuments, setDropship, settleConsignment, uploadProductDocument } from "@/src/modules/inventory/actions/inventory";
import type { ProductDocument } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Input } from "@/src/platform/ui/field";

// Order-on-demand, dropshipping and documents with products (feature plan steps 15b, 15c, 15e).

/** Before approval: whether the vendor ships this order straight to the customer. */
export function DropshipSwitch({ orderId, on }: { orderId: string; on: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  return (
    <Checkbox
      checked={on}
      disabled={busy}
      onChange={(e) =>
        start(async () => {
          const r = await setDropship(orderId, e.target.checked);
          if (!r.ok) return void toast.error(r.error);
          toast.success(e.target.checked ? "The vendor ships it straight to the customer" : "It ships from our warehouse");
          router.refresh();
        })
      }
    >
      Dropship: the vendor delivers straight to the customer
    </Checkbox>
  );
}

/** A placed dropship purchase order: the vendor says it was delivered to our customer. */
export function DropshipDelivered({ poId }: { poId: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  return (
    <Button
      variant="primary"
      loading={busy}
      onClick={() =>
        start(async () => {
          const r = await dropshipDelivered(poId);
          if (!r.ok) return void toast.error(r.error);
          toast.success("Delivered to the customer", { description: "No stock came through us; Finance invoices the sale." });
          router.refresh();
        })
      }
    >
      Vendor delivered it
    </Button>
  );
}

const size = (n: number) => (n > 1_000_000 ? `${(n / 1_000_000).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1000))} KB`);

/** An item's documents: upload, choose which go with every sale, remove. */
export function ProductDocuments({ productId, documents, canEdit }: { productId: string; documents: ProductDocument[]; canEdit: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [name, setName] = useState("");
  const file = useRef<HTMLInputElement>(null);

  function upload() {
    const f = file.current?.files?.[0];
    if (!f) return void toast.error("Choose the file first.");
    const form = new FormData();
    form.append("file", f);
    form.append("name", name.trim());
    form.append("sendWithSales", "true");
    start(async () => {
      const r = await uploadProductDocument(productId, form);
      if (!r.ok) return void toast.error(r.error);
      toast.success("Document added", { description: "It goes with every sale of this item." });
      setName("");
      if (file.current) file.current.value = "";
      router.refresh();
    });
  }

  function run(task: () => Promise<{ ok: boolean; error?: string }>, done: string) {
    start(async () => {
      const r = await task();
      if (!r.ok) return void toast.error(r.error ?? "That didn't work.");
      toast.success(done);
      router.refresh();
    });
  }

  return (
    <div>
      {documents.length === 0 ? (
        <p className="text-meta text-ink-3">None yet. Keep its certificate of analysis, leaflet or CPR certificate here; they go with every sale.</p>
      ) : (
        <ul className="divide-y divide-rule text-sm">
          {documents.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-3 py-1.5">
              <FileText className="size-4 text-ink-3" aria-hidden />
              <a href={d.href} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate font-medium text-hema hover:underline">{d.name}</a>
              <span className="text-meta text-ink-3">{d.fileName} · {size(d.size)}</span>
              {canEdit ? (
                <>
                  <Checkbox checked={d.sendWithSales} disabled={busy} onChange={(e) => run(() => saveProductDocument(productId, d.id, { sendWithSales: e.target.checked }), e.target.checked ? "Goes with every sale" : "Kept here only")}>
                    With every sale
                  </Checkbox>
                  <button suppressHydrationWarning type="button" title={`Remove ${d.name}`} disabled={busy} onClick={() => run(() => deleteProductDocument(productId, d.id), `${d.name} removed`)} className="rounded-md p-1 text-ink-3 hover:text-danger">
                    <Trash2 className="size-4" aria-hidden />
                    <span className="sr-only">Remove {d.name}</span>
                  </button>
                </>
              ) : (
                d.sendWithSales && <span className="text-meta text-ink-3">With every sale</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Input aria-label="Document name" placeholder="Name (e.g. Certificate of analysis)" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className="max-w-xs" />
          <input suppressHydrationWarning ref={file} type="file" accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx" aria-label="File" className="text-sm" />
          <Button size="sm" icon={<Upload className="size-4" aria-hidden />} loading={busy} onClick={upload}>Add document</Button>
        </div>
      )}
    </div>
  );
}

/** The documents that go with a delivery or sales order: its items' ones, and emailing them to the customer. */
export function SaleDocuments({ documents, send }: { documents: (ProductDocument & { product: { name: string } })[]; send?: { kind: "orders" | "sales-orders"; id: string } }) {
  if (documents.length === 0) return null;
  return (
    <div>
      {send && <EmailDocuments kind={send.kind} id={send.id} />}
      <p className="mb-1 text-caps text-ink-3 uppercase">Documents to send with it</p>
      <ul className="text-sm">
        {documents.map((d) => (
          <li key={d.id} className="flex items-center gap-2 py-0.5">
            <FileText className="size-4 text-ink-3" aria-hidden />
            <a href={d.href} target="_blank" rel="noreferrer" className="text-hema hover:underline">{d.name}</a>
            <span className="text-meta text-ink-3">· {d.product.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Emails the documents to the customer, through the company's Email sending service. */
function EmailDocuments({ kind, id }: { kind: "orders" | "sales-orders"; id: string }) {
  const [busy, start] = useTransition();
  const [to, setTo] = useState("");
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const r = await sendSaleDocuments(kind, id, to.split(/[\s,;]+/).filter(Boolean), null);
          if (!r.ok) return void toast.error(r.error);
          toast.success(`${r.data.sent} ${r.data.sent === 1 ? "document" : "documents"} sent`, { description: r.data.to.join(", ") });
          setTo("");
        });
      }}
      className="float-right ml-3 flex items-center gap-2"
    >
      <Input aria-label="Customer's email" type="email" placeholder="customer@company.com" value={to} onChange={(e) => setTo(e.target.value)} className="w-56" />
      <Button type="submit" size="sm" loading={busy} disabled={!to.trim()}>Email them</Button>
    </form>
  );
}

/** Settle a vendor's consignment: what sold since the last settlement goes to Finance as a draft bill. */
export function SettleConsignment({ supplierId, name, disabled }: { supplierId: string; name: string; disabled: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  return (
    <Button
      size="sm"
      variant="primary"
      loading={busy}
      disabled={disabled}
      onClick={() =>
        start(async () => {
          const r = await settleConsignment(supplierId);
          if (!r.ok) return void toast.error(r.error);
          toast.success(`${r.data.number} settled for ${name}`, { description: "Finance has it as a draft bill, for the vendor's invoice number and approval." });
          router.refresh();
        })
      }
    >
      Settle and bill
    </Button>
  );
}
