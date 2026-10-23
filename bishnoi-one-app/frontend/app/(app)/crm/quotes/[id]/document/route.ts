import { enc } from "@/src/platform/lib/api";
import { passFile } from "@/src/modules/crm/routes/pass-file";

// A quote written into an uploaded Excel quotation form (?template=).
export async function GET(request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const template = new URL(request.url).searchParams.get("template");
  const query = template ? `?template=${enc(template)}` : "";
  return passFile(`/quotes/${enc(id)}/document.xlsx${query}`, "Couldn't prepare the Excel quotation.", "attachment");
}
