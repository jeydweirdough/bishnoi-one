"use server";
import { refresh } from "next/cache";
import { api, enc, ApiError } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { BillInput } from "./actions";
import type { Bill } from "./types";
import type { PurchaseAllocationInput, PurchaseIntake } from "./purchase-types";

export async function preparePurchase(requestId: string, allocations: PurchaseAllocationInput[], bill: BillInput): Promise<Result<Bill> & { uncertain?: boolean }> {
  try { const data=await api.post<Bill>("/finance/purchase-intakes/prepare",{requestId,sourceReviewed:true,allocations,bill}); refresh(); return {ok:true,data}; }
  catch(error) {
    if (!(error instanceof ApiError) || error.status>=500) return {ok:false,uncertain:true,error:"The preparation result is unknown. Keep this form and retry the same unchanged request, or check From Inventory before starting another bill."};
    return attempt(async()=>{throw error;});
  }
}
export async function linkPurchaseSupplier(id:string,version:number,supplierId:string,evidence:string):Promise<Result<PurchaseIntake>> {
  return attempt(async()=>{const out=await api.post<PurchaseIntake>(`/finance/purchase-intakes/${enc(id)}/supplier`,{version,supplierId,evidence});refresh();return out;});
}
export async function returnPurchase(id:string,version:number,reason:string):Promise<Result<PurchaseIntake>> {
  return attempt(async()=>{const out=await api.post<PurchaseIntake>(`/finance/purchase-intakes/${enc(id)}/return`,{version,reason});refresh();return out;});
}
export async function resumePurchase(id:string,version:number,reason:string):Promise<Result<PurchaseIntake>> {
  return attempt(async()=>{const out=await api.post<PurchaseIntake>(`/finance/purchase-intakes/${enc(id)}/resume`,{version,reason});refresh();return out;});
}
export async function cancelPurchaseDraft(id:string):Promise<Result<{cancelled:boolean}>> {
  return attempt(async()=>{const out=await api.post<{cancelled:boolean}>(`/finance/purchase-intakes/bills/${enc(id)}/cancel-draft`,{});refresh();return out;});
}
