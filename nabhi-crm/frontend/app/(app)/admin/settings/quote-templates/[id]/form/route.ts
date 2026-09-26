import { enc } from "@/src/platform/lib/api";
import { passFile } from "@/src/routes/pass-file";

// The Excel form as it was uploaded.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  return passFile(`/admin/quote-templates/${enc(id)}/excel`, "Couldn't open the form.", "attachment");
}
