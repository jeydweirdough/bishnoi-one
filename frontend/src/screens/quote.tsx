import { ApprovalActions, LetterActions, PaymentForm } from "@/src/vendor-finance/components/finance-actions";
import { DeleteQuote } from "../components/delete-quote";
import { RaiseOrder } from "../components/raise-order";
import { QuoteView } from "../components/quote-view";
import { QuoteStateMark } from "@/src/platform/ui/marks";
import { PageHeader } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Quote } from "@/src/platform/lib/types";

// One page for a quote, read two ways: by the rep whose customer it belongs to,
// and by Finance, who sees it across divisions and acts on it. Which one it is
// comes from where the reader arrived: Finance reaches a quote from one of its
// lists, and that list is also the crumb back.
const FINANCE_LISTS = { approvals: "Approvals", letters: "Guarantee letters", payments: "Letter payments" } as const;
type FinanceList = keyof typeof FINANCE_LISTS;

const cameFromFinance = (from: string | undefined): from is FinanceList => !!from && from in FINANCE_LISTS;
const path = (finance: boolean, id: string) => (finance ? `/finance/quotes/${enc(id)}` : `/sales/quotes/${enc(id)}`);

export async function generateMetadata({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [{ id }, search] = await Promise.all([params, searchParams]);
  const quote = await load<Quote>(path(cameFromFinance(search.from as string | undefined), id));
  return { title: `Quote ${quote.number}` };
}

export default async function QuotePage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [{ id }, search] = await Promise.all([params, searchParams]);
  const finance = cameFromFinance(search.from as string | undefined);
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const quote = await load<Quote>(path(finance, id));
  const letterHref = `/quotes/${id}/letter${finance ? "?from=" + search.from : ""}`;
  // Finance arrives from one of its lists; the crumb goes back to the one this quote is waiting in.
  const crumbs = finance
    ? [
        { href: "/m/finance", label: "Finance" },
        { href: `/m/finance/${search.from}`, label: FINANCE_LISTS[search.from as FinanceList] },
      ]
    : [
        { href: "/customers", label: "Customers" },
        { href: `/customers/${quote.customerId}`, label: quote.customerName ?? "Customer" },
      ];

  return (
    <>
      <PageHeader
        crumbs={crumbs}
        title={`Quote ${quote.number}`}
        actions={
          !finance && (
            <>
              {/* The common next step after a quote is agreed, so it sits where
                  the eye lands first. */}
              <RaiseOrder quote={quote} ordersUrl={me.modules.find((m) => m.key === "orders")?.url} />
              {quote.can.delete && <DeleteQuote id={id} number={quote.number} customerId={quote.customerId} />}
            </>
          )
        }
      >
        <span className="inline-flex flex-wrap items-center gap-2">
          <QuoteStateMark state={quote.state} />
          <span>
            {[quote.customerName, finance ? `${quote.divisionName} · ${quote.teamName}` : null, fmt.peso(quote.totalCentavos)].filter(Boolean).join(" · ")}
          </span>
        </span>
      </PageHeader>
      <QuoteView
        quote={quote}
        letterHref={letterHref}
        customerHref={finance ? undefined : `/customers/${quote.customerId}`}
        actions={
          finance
            ? {
                approval: <ApprovalActions quote={quote} org={me.org} />,
                letter: <LetterActions quote={quote} org={me.org} />,
                payment: <PaymentForm quote={quote} org={me.org} />,
              }
            : undefined
        }
      />
    </>
  );
}
