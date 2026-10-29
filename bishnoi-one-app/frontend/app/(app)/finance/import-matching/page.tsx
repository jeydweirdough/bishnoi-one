import {getCompanyMe,load} from '@/src/modules/finance/platform/lib/api';
import {PageHeader,Sheet} from '@/src/modules/finance/platform/ui/sheet';
import {ImportMatching} from '@/src/modules/finance/import-matching/matching';
import {IMPORT_TICKS,type Matching} from '@/src/modules/finance/import-matching/types';
export const metadata={title:'Import matching'};
export default async function Page(){
 const me=await getCompanyMe();
 const allowed=IMPORT_TICKS.some(tick=>me.permissions?.includes(tick));
 const header=<PageHeader title="Import matching">Match each label from the Zoho exports once; someone proposes, someone else confirms; only confirmed matches are used by imports.</PageHeader>;
 if(!allowed)return <>{header}<Sheet className="p-5">Import matching requires one of the Imports permissions. Ask the company administrator to assign access.</Sheet></>;
 const data=await load<Matching>('/finance/imports/matching');
 return <>{header}<ImportMatching data={data}/></>;
}
