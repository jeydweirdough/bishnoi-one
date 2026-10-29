import {relay} from '@/src/modules/finance/import-matching/relay';
// ?kind=bills|supplier-payments and ?step=preview|import: only these four API paths.
export async function POST(request:Request){
 const params=new URL(request.url).searchParams;const kind=params.get('kind'),step=params.get('step');
 if((kind!=='bills'&&kind!=='supplier-payments')||(step!=='preview'&&step!=='import'))return Response.json({detail:'Unknown import.'},{status:404});
 return relay(request,`/finance/imports/${kind}${step==='preview'?'/preview':''}`);
}
