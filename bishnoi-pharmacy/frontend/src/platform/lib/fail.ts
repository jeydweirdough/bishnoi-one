import "server-only";
import { forbidden, notFound, redirect } from "next/navigation";

// Where a page that couldn't be read sends the person: each kind of failure to
// a page of its own, said plainly (src/platform/screens/error-screen.tsx). A
// record out of someone's reach is already a 404 from the API, so "no access"
// never tells anyone that a record exists.
//
// The same file is in every app's shared kit (src/platform/lib/fail.ts).

/** Sends the person to the page for this status. Anything else returns, for the caller's own error page. */
export function sendToErrorPage(status: number | undefined): void {
  if (status === 401) redirect("/login?expired=1");
  if (status === 403) forbidden();
  if (status === 404) notFound();
  if (status === 429) redirect("/busy");
  if (status === 502 || status === 503 || status === 504) redirect("/unavailable");
}
