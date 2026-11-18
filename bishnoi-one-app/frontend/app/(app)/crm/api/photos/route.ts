import { api, ApiError } from "@/src/platform/lib/api";

// A visit's photo from a field agent's offline queue (Step 4H): file,
// targetId and the phone's clientId (sent twice, kept once).
export async function POST(request: Request) {
  let given: FormData;
  try {
    given = await request.formData();
  } catch {
    return Response.json({ detail: "Send the photo as a form." }, { status: 400 });
  }
  const file = given.get("file");
  const targetId = given.get("targetId");
  if (!(file instanceof Blob) || typeof targetId !== "string") return Response.json({ detail: "Send the photo and its visit." }, { status: 400 });
  const form = new FormData();
  form.append("file", file, file instanceof File ? file.name : "photo.jpg");
  form.append("targetType", "visit");
  form.append("targetId", targetId);
  const clientId = given.get("clientId");
  if (typeof clientId === "string") form.append("clientId", clientId);
  try {
    return Response.json(await api.upload("/photos", form));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 502;
    return Response.json({ detail: error instanceof ApiError ? error.detail : "Couldn't reach the API." }, { status });
  }
}
