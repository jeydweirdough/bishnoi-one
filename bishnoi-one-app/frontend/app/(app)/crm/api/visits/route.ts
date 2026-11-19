import { api, ApiError } from "@/src/platform/lib/api";

// A visit kept on a field agent's phone while it was offline (Step 4H,
// src/modules/crm/components/field/offline-queue.ts), sent once it's back
// online. It carries the phone's clientId: sent twice, the API keeps one.
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ detail: "Send the visit as JSON." }, { status: 400 });
  }
  try {
    return Response.json(await api.post("/visits", body));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return Response.json({ detail: error instanceof ApiError ? error.detail : "Couldn't reach the API." }, { status });
  }
}
