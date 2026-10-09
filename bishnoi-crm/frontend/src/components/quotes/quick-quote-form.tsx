"use client";

import { useRouter } from "next/navigation";
import { quickQuote } from "../../actions/quote-links";
import { MedicineSearch, type Medicine } from "./medicine-search";

/** A rep's quick quote: picked from the medicine search, saved as a quote, then its quotation letter. */
export function QuickQuoteForm({ companyId, priceType, medicines }: { companyId: string; priceType: string; medicines: Medicine[] }) {
  const router = useRouter();
  return (
    <MedicineSearch
      medicines={medicines}
      submitLabel="Make the quote"
      onSubmit={async (lines) => {
        const r = await quickQuote(companyId, priceType, lines);
        if (!r.ok) return r.error;
        // Ready: straight to its letter. Waiting for approval: its page, which says who it waits on.
        router.push(r.data.ready ? `/print/quotes/${r.data.id}` : `/quotes/${r.data.id}`);
        return null;
      }}
    />
  );
}
