import { notFound, redirect } from "next/navigation";
import { ApiError, api, enc, load } from "@/src/platform/lib/api";

/**
 * A customer or contact by id, as load() does it; but an id that was merged
 * into another (Customers → Possible duplicates) goes to the one kept, so old
 * links and bookmarks still work.
 */
export async function loadRecord<T>(path: "companies" | "contacts", id: string): Promise<T> {
  try {
    return await api.get<T>(`/${path}/${enc(id)}`);
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 404)) return load<T>(`/${path}/${enc(id)}`);
  }
  const merged = await api.get<{ newId: string }>(`/merged/${enc(id)}`).catch(() => null);
  if (merged) redirect(`/${path}/${merged.newId}`);
  notFound();
}
