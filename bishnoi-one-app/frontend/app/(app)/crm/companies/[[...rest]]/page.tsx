// Customers live at /crm/customers (decided 2026-10-26: a customer may be a person, not only a
// company). Links and bookmarks to the old /crm/companies addresses go to the same page there.
import { redirect } from "next/navigation";

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ rest?: string[] }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { rest = [] } = await params;
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(await searchParams)) for (const one of Array.isArray(v) ? v : v ? [v] : []) q.append(k, one);
  redirect(`/crm/customers${rest.length ? `/${rest.map(encodeURIComponent).join("/")}` : ""}${q.size ? `?${q}` : ""}`);
}
