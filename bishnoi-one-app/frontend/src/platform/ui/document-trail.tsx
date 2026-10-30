import Link from "next/link";
import type { ComponentType } from "react";
import { ArrowRight } from "lucide-react";
import { accountSend } from "@/src/platform/lib/account";

// The document trail (feature plan step 9, pattern P16): the documents before and after one, across
// every app (the Platform keeps the chain, /identity/documents/trail), each one click away. Only
// numbers and links: each app still decides who may open each document.

type DocRef = { app: string; kind: string; id: string; number: string | null };
type Trail = { document: DocRef; before: DocRef[]; after: DocRef[]; related: DocRef[] };

/** Where each kind of document opens in the one app, and what it's called. */
const PAGES: Record<string, { path: string; label: string }> = {
  "inventory:purchase_order": { path: "/inventory/purchase-orders/", label: "Purchase order" },
  "inventory:receipt": { path: "/inventory/receipts/", label: "Purchase receive" },
  "inventory:sales_order": { path: "/crm/sales/orders/", label: "Sales order" },
  "inventory:order": { path: "/inventory/orders/", label: "Delivery" },
  "inventory:transfer": { path: "/inventory/transfers/", label: "Transfer order" },
  "inventory:adjustment": { path: "/inventory/adjustments/", label: "Adjustment" },
  "inventory:count": { path: "/inventory/counts/", label: "Inventory count" },
  "finance:invoice": { path: "/finance/invoices/", label: "Invoice" },
  "crm:deal": { path: "/crm/deals/", label: "Deal" },
  "crm:quote": { path: "/crm/quotes/", label: "Quote" },
};

function Doc({ d, current = false }: { d: DocRef; current?: boolean }) {
  const page = PAGES[`${d.app}:${d.kind}`];
  const label = page?.label ?? d.kind.replace(/_/g, " ");
  const inner = (
    <>
      <span className="block text-meta text-ink-3">{label}</span>
      <span className="block truncate text-sm font-semibold">{d.number ?? "Draft"}</span>
    </>
  );
  const look = `block min-w-[8.5rem] max-w-[14rem] rounded-lg border px-3 py-1.5 ${current ? "border-hema bg-hema-tint text-ink" : "border-rule-strong bg-sheet text-ink hover:border-hema"}`;
  if (current || !page) return <span className={look} aria-current={current ? "page" : undefined}>{inner}</span>;
  return (
    <Link href={`${page.path}${d.id}`} className={look}>
      {inner}
    </Link>
  );
}

/** The chain for one document; nothing when it isn't linked to anything (or the Platform can't be reached). */
export async function DocumentTrail({ app, kind, id }: { app: string; kind: string; id: string }) {
  let t: Trail;
  try {
    t = await accountSend<Trail>("GET", `/identity/documents/trail?app=${encodeURIComponent(app)}&kind=${encodeURIComponent(kind)}&id=${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
  if (t.before.length === 0 && t.after.length === 0 && t.related.length === 0) return null;
  const chain = [...t.before, t.document, ...t.after];
  return (
    <section aria-label="Document trail" className="mt-6 rounded-xl border border-rule bg-sheet px-5 py-4">
      <h2 className="mb-3 text-caps text-ink-3 uppercase">Document trail</h2>
      <ol className="flex flex-wrap items-center gap-2">
        {chain.map((d, i) => (
          <li key={`${d.app}:${d.kind}:${d.id}`} className="flex items-center gap-2">
            {i > 0 && <ArrowRight className="size-4 text-ink-3" aria-hidden />}
            <Doc d={d} current={d.id === t.document.id && d.kind === t.document.kind && d.app === t.document.app} />
          </li>
        ))}
      </ol>
      {t.related.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-meta text-ink-3">Also from the same source</p>
          <ul className="flex flex-wrap gap-2">
            {t.related.map((d) => (
              <li key={`${d.app}:${d.kind}:${d.id}`}>
                <Doc d={d} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

type RecordProps = { params: Promise<{ id: string }>; searchParams?: Promise<Record<string, string | string[] | undefined>> };

/** A record page with its document trail at the foot: the screen as it is, then the chain. */
export function withTrail<P extends RecordProps>(Screen: (props: P) => unknown, app: string, kind: string) {
  const Shown = Screen as unknown as ComponentType<P>;
  return async function RecordWithTrail(props: P) {
    const { id } = await props.params;
    return (
      <>
        <Shown {...props} />
        <DocumentTrail app={app} kind={kind} id={id} />
      </>
    );
  };
}
