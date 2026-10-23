import { enc } from "@/src/platform/lib/api";
import { passFile } from "@/src/modules/crm/routes/pass-file";

// A quotation template's logo or e-signature, for the print page and Settings.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string; which: string }> }) {
  const { id, which } = await ctx.params;
  return passFile(`/quote-templates/${enc(id)}/images/${enc(which)}`, "Couldn't open the image.");
}
