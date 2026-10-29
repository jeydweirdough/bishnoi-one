import {relay} from '@/src/modules/finance/import-matching/relay';
// ?id=<match id>: the records behind one label, read from the exports sent (nothing is saved).
export async function POST(request:Request){
 const id=new URL(request.url).searchParams.get('id')||'';
 if(!/^[0-9a-f-]{36}$/.test(id))return Response.json({detail:'Unknown label.'},{status:404});
 return relay(request,`/finance/imports/matching/${id}/records`);
}
