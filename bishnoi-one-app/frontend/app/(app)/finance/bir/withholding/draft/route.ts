import { ApiError, fetchFile } from "@/src/modules/finance/platform/lib/api";
export async function GET(request: Request) {
  const asked=new URL(request.url).searchParams;
  const form=asked.get("form") ?? "";
  if (!["2307","0619e","1601eq","1604e"].includes(form)) return new Response("Choose a listed form.",{status:400});
  const query=new URLSearchParams();
  for (const key of ["year","quarter","month","supplierId"]) if(asked.get(key))query.set(key,asked.get(key)!);
  if(form==="2307" && !query.get("supplierId"))return new Response("Choose the payee first.",{status:400});
  try {
    const file=await fetchFile(`/finance/bir/withholding/${form}/draft.pdf?${query}`);
    return new Response(file.body,{headers:{"Content-Type":"application/pdf","Content-Disposition":file.headers.get("content-disposition")??"attachment","Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"}});
  } catch(error) {
    return new Response(error instanceof ApiError && typeof error.detail==="string" ? error.detail : "Could not prepare the PDF.",{status:error instanceof ApiError?error.status:500});
  }
}
