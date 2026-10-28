import {NextResponse,type NextRequest} from 'next/server';
import {apiFor} from '@/src/platform/lib/api';

// Never render codes, log querystrings, or return provider/token payloads to the browser.
export async function GET(request:NextRequest){
 let result='failed';
 try{
  const q=request.nextUrl.searchParams;
  await apiFor('finance').post('/finance/integrations/zoho/callback',{
   state:q.get('state')??'',code:q.get('code'),error:q.get('error'),
  });
  result='connected';
 }catch{/* The status page uses a fixed safe message; no codes or provider errors. */}
 const response=NextResponse.redirect(new URL(`/finance/integrations/zoho?result=${result}`,request.url),303);
 response.headers.set('Cache-Control','no-store');
 response.headers.set('Referrer-Policy','no-referrer');
 return response;
}
