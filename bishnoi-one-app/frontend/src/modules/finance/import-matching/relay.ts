import 'server-only';
import {api,ApiError} from '@/src/modules/finance/platform/lib/api';

// The Zoho export files are larger than a server action takes, so the screens post them to a
// route of this site, which checks where the request came from and its size, then passes it on
// (as app/(app)/finance/import-review/load/route.ts does).
export async function relay(request:Request,path:string):Promise<Response>{
 if(request.headers.get('origin')!==new URL(request.url).origin)return Response.json({detail:'Open this from the Finance site.'},{status:403});
 try{
  const reader=request.body?.getReader();if(!reader)return Response.json({detail:'Choose the two CSV files first.'},{status:422});
  const chunks:Uint8Array[]=[];let size=0;
  while(true){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;if(size>18*1024*1024){await reader.cancel();return Response.json({detail:'This request exceeds 18 MB. Choose smaller exports.'},{status:413});}chunks.push(part.value);}
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
  let body:unknown;try{body=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{return Response.json({detail:'The request is not valid JSON.'},{status:422});}
  const result=await api.post(path,body);
  return Response.json(result,{headers:{'Cache-Control':'no-store'}});
 }catch(error){if(error instanceof ApiError)return Response.json({detail:typeof error.detail==='string'?error.detail:'Some fields are invalid. Choose the two files again.'},{status:error.status});return Response.json({detail:'This could not finish. Your existing records were not changed.'},{status:503});}
}
