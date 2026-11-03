import { download } from "@/src/modules/finance/exports/download";
const records = new Set(["bills", "bill-lines", "invoices", "customer-payments", "supplier-payments", "payment-allocations", "petty-cash", "petty-cash-lines", "imported-expenses", "imported-expense-lines"]);
const reports = new Set(["vat", "vat-sources", "0619e", "1601eq", "2307", "withholding-sources"]);
export function GET(request: Request) {
  const query = new URL(request.url).searchParams;
  const kind = query.get("kind") ?? "";
  if (!records.has(kind) && !reports.has(kind)) return new Response("Pick a listed export.", { status: 400 });
  query.delete("kind");
  for (const key of ["start", "end"]) if (!query.get(key)) query.delete(key);
  return download(`/finance/exports/${reports.has(kind) ? "bir-review" : "review"}/${kind}.csv`, `?${query}`);
}
