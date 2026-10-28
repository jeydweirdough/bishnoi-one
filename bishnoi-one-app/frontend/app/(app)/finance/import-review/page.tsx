import {getCompanyMe} from '@/src/modules/finance/platform/lib/api';
import {PageHeader} from '@/src/modules/finance/platform/ui/sheet';
import {ImportReview} from '@/src/modules/finance/import-review/review';
export const metadata={title:'Q1 import review'};
export default async function Page(){
 const me=await getCompanyMe();
 return <><PageHeader title="Q1 import review">Read the Zoho transactions, connect their records, and compare the Oojeema balances before anything enters the books.</PageHeader><ImportReview allowed={Boolean(me.permissions?.includes('integrations.manage'))} environment={me.dataEnvironment||'local_test'}/></>;
}
