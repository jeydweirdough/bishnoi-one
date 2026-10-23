import { Suspense, type ReactNode } from "react";

/**
 * Part of a server screen that waits for its records while the rest of the page
 * (title, filters, cards) is already drawn. Start the request without awaiting
 * it, then: <Later data={answer} fallback={<ListRows />}>{(a) => …rows…}</Later>.
 * The same promise can feed several Laters (the count in the header and the
 * rows below); it is asked for once. Server screens only (the children run there).
 */
export function Later<T>({ data, fallback, children }: { data: Promise<T>; fallback: ReactNode; children: (value: T) => ReactNode }) {
  return <Suspense fallback={fallback}>{data.then(children)}</Suspense>;
}
