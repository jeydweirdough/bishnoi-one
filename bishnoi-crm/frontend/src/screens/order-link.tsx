import { ApiError, api } from "@/src/platform/lib/api";
import { COMPANY_HEADER } from "@/src/platform/lib/session-cookie";
import { EmptyDrawing } from "@/src/platform/ui/empty-drawings";
import { OrderLinkForm } from "../components/quotes/order-link-form";
import type { Medicine } from "../components/quotes/medicine-search";
import type { LinkAsks } from "../actions/quote-links";

export const metadata = { title: "Order medicines", robots: { index: false, follow: false } };

type Link = { company: string; orgName: string; customer: string | null; contact: string | null; asksWho: boolean; rep: string; expiresAt: string; products: Omit<Medicine, "priceCentavos">[]; asks: LinkAsks; uploads: "direct" | "with-order" };
type Params = Promise<{ company: string; token: string }>;

const until = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Manila" });

/**
 * The page an order link opens, with no account: the medicines at this
 * customer's prices, picked and sent to their medical representative. A link
 * that's used, expired or switched off says so, and how to get a new one.
 */
export default async function OrderLinkPage({ params }: { params: Params }) {
  const { company, token } = await params;
  let link: Link | null = null;
  let gone = "";
  try {
    link = await api.get<Link>(`/public/quote-links/${encodeURIComponent(token)}`, { [COMPANY_HEADER]: company });
  } catch (e) {
    gone = e instanceof ApiError && typeof e.detail === "string" ? e.detail : "This link can't be opened right now. Try again in a moment.";
  }

  return (
    <main className="min-h-dvh bg-bench px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl">
        {!link ? (
          <section className="mx-auto mt-16 max-w-md rounded-sheet border border-rule bg-sheet p-8 text-center">
            <EmptyDrawing icon="quotes" className="mx-auto h-[92px] w-[120px]" />
            <h1 className="mt-3 text-heading text-ink">This link doesn&apos;t open any more</h1>
            <p className="mt-1 text-sm text-ink-2">{gone}</p>
          </section>
        ) : (
          <>
            <header className="mb-6">
              <p className="text-caps text-ink-3 uppercase">{link.orgName}</p>
              <h1 className="mt-1 text-[2rem] leading-tight font-semibold text-ink">Order your medicines</h1>
              <p className="mt-1 text-sm text-ink-2">
                {link.customer ? `For ${link.contact ? `${link.contact}, ${link.customer}` : link.customer} · ` : ""}From {link.rep}, your medical representative · the link works until{" "}
                {until.format(new Date(link.expiresAt))}, once.
              </p>
            </header>
            <OrderLinkForm company={company} orgName={link.orgName} token={token} medicines={link.products.map((m) => ({ ...m, priceCentavos: 0 }))} rep={link.rep} asksWho={link.asksWho} asks={link.asks} uploads={link.uploads} />
          </>
        )}
      </div>
    </main>
  );
}
