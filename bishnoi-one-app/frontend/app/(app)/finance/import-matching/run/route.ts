import {relay} from '@/src/modules/finance/import-matching/relay';
// ?kind=bills|supplier-payments|oojeema-sales|expenses and ?step=preview|import: only these API paths.
export async function POST(request:Request){
 const params=new URL(request.url).searchParams;const kind=params.get('kind'),step=params.get('step');
 if(!['bills','supplier-payments','oojeema-sales','expenses'].includes(kind??'')||(step!=='preview'&&step!=='import'))return Response.json({detail:'Unknown import.'},{status:404});
 return relay(request,`/finance/imports/${kind}${step==='preview'?'/preview':''}`);
}
