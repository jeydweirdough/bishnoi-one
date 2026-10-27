import { Printer } from "lucide-react";
import { ApprovalActions, CreditActions, LetterActions, PaymentForm } from "@/src/modules/crm/vendor-finance/components/finance-actions";
import { DeleteQuote } from "@/src/modules/crm/components/delete-quote";
import { PharmacyCheckForm } from "@/src/modules/crm/components/pharmacy-check";
import { RaiseOrder } from "@/src/modules/crm/components/raise-order";
import { QuoteView } from "@/src/modules/crm/components/quote-view";
import { customFields } from "@/src/modules/crm/components/extra/load";
import { QuoteStateMark } from "@/src/platform/ui/marks";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Quote } from "@/src/platform/lib/types";

// One page for a quote, for the rep whose customer it is and for whoever
// approves it. An approver arriving from one of the Quotes lists (?from=approvals)
// gets that list as the crumb back; everyone else gets the customer.
const LISTS = { approvals: "To approve", letters: "Letters to check", payments: "Letter payments" } as const;
type List = keyof typeof LISTS;

const fromList = (from: unknown): from is List => typeof from === "string" && from in LISTS;

type Params = Promise<{ id: string }>;
type Search = Promise<Record<string, string | string[] | undefined>>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: `Quote ${(await load<Quote>(`/quotes/${enc(id)}`)).number}` };
  } catch {
    return { title: "Quote" };
  }
}

export default async function QuotePage({ params, searchParams }: { params: Params; searchParams: Search }) {
  const [{ id }, search] = await Promise.all([params, searchParams]);
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const [quote, fields] = await Promise.all([load<Quote>(`/quotes/${enc(id)}`), customFields("quote")]);
  const from = search.from;
  const customer = quote.contact ?? quote.company;
  const crumbs = fromList(from)
    ? [
        { href: "/crm/quotes", label: "Quotes" },
        { href: `/crm/quotes?task=${from}`, label: LISTS[from] },
      ]
    : customer && quote.customerHref
      ? [
          { href: quote.contact ? "/crm/contacts" : "/crm/customers", label: quote.contact ? "Contacts" : "Customers" },
          { href: quote.customerHref, label: customer.name },
        ]
      : [{ href: "/crm/quotes", label: "Quotes" }];

  return (
    <>
      <PageHeader
        crumbs={crumbs}
        title={`Quote ${quote.number}`}
        actions={
          <>
            {/* The common next step after a quote is agreed, so it sits where the eye lands first. */}
            <LinkButton href={`/crm/print/quotes/${id}`} icon={<Printer className="size-4" aria-hidden />} prefetch={false}>
              Print
            </LinkButton>
            <RaiseOrder quote={quote} linked={!!me.ordersLinked} mayOrder={!!me.permissions?.includes("orders.create")} />
            {quote.can.delete && <DeleteQuote id={id} number={quote.number} leaveTo={quote.customerHref ?? "/crm/quotes"} />}
          </>
        }
      >
        <span className="inline-flex flex-wrap items-center gap-2">
          <QuoteStateMark state={quote.state} />
          <span>{[quote.customerName, quote.teamName, fmt.peso(quote.totalCentavos)].filter(Boolean).join(" · ")}</span>
        </span>
      </PageHeader>
      <QuoteView
        quote={quote}
        letterHref={`/crm/quotes/${id}/letter`}
        customerHref={quote.customerHref ?? undefined}
        fields={fields}
        actions={{
          approval: <ApprovalActions quote={quote} org={me.org} />,
          credit: <CreditActions quote={quote} org={me.org} />,
          letter: <LetterActions quote={quote} org={me.org} />,
          payment: <PaymentForm quote={quote} org={me.org} />,
          pharmacy: <PharmacyCheckForm quote={quote} org={me.org} linked={!!me.pharmacyLinked} />,
        }}
      />
    </>
  );
}
