import Link from "next/link";
import { PageHeader } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe,load } from "@/src/modules/finance/platform/lib/api";
import { BillEditor } from "@/src/modules/finance/payables/bill-editor";
import { PurchaseQueueView,PurchaseReview } from "@/src/modules/finance/payables/purchase-queue";
import { screen } from "@/src/modules/finance/lib/links";
import type { PurchaseQueue,PurchaseIntake,PurchaseSource } from "@/src/modules/finance/payables/purchase-types";
import type { BillChoices } from "@/src/modules/finance/payables/types";

export default async function PurchaseIntakesPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
  const sp=await searchParams;const offset=typeof sp.offset==='string'&&/^\d+$/.test(sp.offset)?Math.min(Number(sp.offset),1000000):0;
  const queue=await load<PurchaseQueue>(`/finance/purchase-intakes?offset=${offset}&limit=50`);
  return <><PageHeader title="From Inventory" crumbs={[{href:screen('/bills'),label:'Bills'}]}>Actual received quantities sent for Finance validation. No accounting entry or payment is created by sending a receipt.</PageHeader><PurchaseQueueView queue={queue}/></>;
}
export async function PurchaseIntakePage({params}:{params:Promise<{id:string}>}) {
  const {id}=await params;
  const [item,choices]=await Promise.all([load<PurchaseIntake&{canPrepare:boolean;canLinkSupplier:boolean}>(`/finance/purchase-intakes/${encodeURIComponent(id)}`),load<BillChoices>('/finance/bills/choices')]);
  return <><PageHeader title={`Received purchase ${item.snapshot.receiptNumber}`} crumbs={[{href:screen('/purchase-intakes'),label:'From Inventory'}]}>Review the received evidence, supplier identity and invoice before preparing a bill.</PageHeader><PurchaseReview item={item} suppliers={choices.suppliers} canLink={item.canLinkSupplier} canPrepare={item.canPrepare}/></>;
}
export async function PreparePurchasePage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
  const sp=await searchParams;const ids=typeof sp.ids==='string'?sp.ids.split(',').slice(0,100):[];
  const [picks,choices,me]=await Promise.all([Promise.all([...new Set(ids)].map(id=>load<PurchaseIntake&{canPrepare:boolean}>(`/finance/purchase-intakes/${encodeURIComponent(id)}`))),load<BillChoices>('/finance/bills/choices'),getCompanyMe()]);
  const first=picks[0];
  if(!first?.canPrepare||!first?.supplier||picks.length!==new Set(ids).size||picks.some(x=>!x.supplier||x.supplier.id!==first.supplier!.id||x.snapshot.currencyEvidence!==first.snapshot.currencyEvidence||x.holds.length||x.remaining===0)) return <><PageHeader title="Review received purchases first"/><p>Select reviewed receipts for one verified supplier and currency. <Link className="underline" href={screen('/purchase-intakes')}>Return to From Inventory</Link></p></>;
  const source:PurchaseSource={supplierId:first.supplier.id,currency:first.snapshot.currencyEvidence,rows:picks.flatMap(x=>x.lines.filter(l=>l.remaining>0).map(l=>({intakeId:x.id,sourceLineId:l.id,version:x.version,quantity:l.remaining,maximum:l.remaining,label:`${x.snapshot.receiptNumber}: ${l.product}`,unit:l.unit,unitCost:l.unitCost})))};
  if(source.rows.length>100)return <p>Select fewer receipt lines; a bill supports at most 100 lines.</p>;
  return <><PageHeader title="Prepare bill from Inventory" crumbs={[{href:screen('/purchase-intakes'),label:'From Inventory'}]}>Received quantities stay linked to this draft. Compare invoice quantities and prices; source costs are evidence and do not establish the invoice tax treatment.</PageHeader><BillEditor bill={null} choices={choices} org={me.org} purchase={source}/></>;
}
