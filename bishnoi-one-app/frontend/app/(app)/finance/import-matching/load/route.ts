import {relay} from '@/src/modules/finance/import-matching/relay';
export async function POST(request:Request){
 return relay(request,'/finance/imports/matching/load');
}
