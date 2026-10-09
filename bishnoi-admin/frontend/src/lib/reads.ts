import "server-only";
import { cache } from "react";
import type { RecordPage } from "@/src/actions/operations";
import { loadQuery } from "@/src/platform/lib/api";

/** One vehicle, fuel card, sponsorship or device issue, with its history: the page and its title share the read. */
export const readRecord = cache(async (path: string, id: string): Promise<RecordPage> =>
  (await loadQuery<{ record: RecordPage }>(`query Record($path: String!, $id: String!) { record(path: $path, id: $id) }`, { path, id }, ["record"])).record,
);
