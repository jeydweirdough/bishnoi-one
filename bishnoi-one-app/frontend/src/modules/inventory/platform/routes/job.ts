import { ApiError, api, enc } from "@/src/modules/inventory/platform/lib/api";
import type { Job } from "@/src/modules/inventory/platform/lib/types";

// A bulk action's progress, for the page that started it. A GET route rather
// than a server action: Next runs server actions one at a time per tab, and
// polling through them would hold up everything else the person clicks.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const job = await api.get<Job>(`/jobs/${enc(id)}`);
    return Response.json(job, { headers: { "Cache-Control": "private, no-store" } });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't check on that job.";
    return Response.json({ detail: message }, { status, headers: { "Cache-Control": "private, no-store" } });
  }
}
