import {api,ApiError} from '@/src/modules/finance/platform/lib/api';
export async function POST(request:Request){
 if(request.headers.get('origin')!==new URL(request.url).origin)return Response.json({detail:'Open this review from the Finance site.'},{status:403});
 try{
  const reader=request.body?.getReader();if(!reader)return Response.json({detail:'Choose CSV files first.'},{status:422});
  const chunks:Uint8Array[]=[];let size=0;
  while(true){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;if(size>12*1024*1024){await reader.cancel();return Response.json({detail:'This request exceeds 12 MB. Choose a smaller CSV pack.'},{status:413});}chunks.push(part.value);}
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
  let body:unknown;try{body=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch{return Response.json({detail:'The review request is not valid JSON.'},{status:422});}
  const rehearse=new URL(request.url).searchParams.get('rehearse')==='1';
  const result=await api.post(`/finance/import-review${rehearse?'/rehearse':''}`,body);
  return Response.json(result,{headers:{'Cache-Control':'no-store'}});
 }catch(error){if(error instanceof ApiError)return Response.json({detail:typeof error.detail==='string'?error.detail:'Some review fields are invalid. Reload the files and check your choices.'},{status:error.status});return Response.json({detail:'The review could not finish. Your existing records were not changed.'},{status:503});}
}
