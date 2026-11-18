import { accountToken, PLATFORM_API } from "@/src/platform/lib/account";

// One HR document (step 4I), opened through the one app: the browser never calls the Platform. The Platform
// refuses anyone but HR and administrators, and logs the opening; nothing is cached on the way.
export async function GET(_: Request, { params }: { params: Promise<{ person: string; doc: string }> }) {
  const { person, doc } = await params;
  const token = await accountToken();
  if (!token) return new Response("Please sign in.", { status: 401 });
  let answer: Response;
  try {
    answer = await fetch(`${PLATFORM_API}/identity/access/people/${encodeURIComponent(person)}/hr/documents/${encodeURIComponent(doc)}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    return new Response("Bishnoi One can't be reached right now.", { status: 503 });
  }
  if (!answer.ok) {
    const data = await answer.json().catch(() => null);
    return new Response(typeof data?.detail === "string" ? data.detail : "That document can't be opened.", { status: answer.status });
  }
  return new Response(answer.body, {
    headers: {
      "Content-Type": answer.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": answer.headers.get("content-disposition") ?? "inline",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
