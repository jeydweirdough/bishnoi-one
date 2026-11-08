import Link from "next/link";
import { Suspense } from "react";
import { load } from "@/src/modules/finance/platform/lib/api";
import type { WaitingPrices } from "@/src/modules/finance/dashboard/types";

// The CRM's prices and quotes waiting for Finance. Asked on their own, after the page is on its way, and
// kept a minute by the API, so the CRM can never slow or break the Overview.

async function Asked() {
  let found: WaitingPrices;
  try {
    found = await load<WaitingPrices>("/finance/dashboard/waiting-prices");
  } catch {
    return <>Prices: not available now</>;
  }
  if (!found.available) return <>Prices: not available now</>;
  const n = found.prices + found.quotes;
  return <Link href="/finance/prices">{n.toLocaleString("en-PH")} {n === 1 ? "price or quote" : "prices and quotes"} to approve →</Link>;
}

export function PricesWaiting() {
  return (
    <Suspense fallback={<>Asking the CRM for prices…</>}>
      <Asked />
    </Suspense>
  );
}
