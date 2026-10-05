import { api, ApiError } from "@/src/platform/lib/api";

// A field agent's trail, from the phone to the API. The browser never talks
// to the API itself, so its batches come through here with the signed-in
// person's token (the phone also sends one here as the page closes).
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ detail: "Send the points as JSON." }, { status: 400 });
  }
  try {
    return Response.json(await api.post("/field/trail", body));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return Response.json({ detail: error instanceof ApiError ? error.detail : "Couldn't reach the API." }, { status });
  }
}
