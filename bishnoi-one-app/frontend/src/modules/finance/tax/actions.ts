"use server";

import { refresh } from "next/cache";
import { api } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { ComputedSale, SaleInput, TaxSetup } from "@/src/modules/finance/tax/types";

// Tax. The API checks who may change what (admins: the registration and
// rates) and every rule; these carry the request and hand back its answer.

export type ProfileInput = {
  country: string;
  regime: string;
  registeredName: string | null;
  tradeName: string | null;
  tin: string | null;
  branchCode: string | null;
  registeredAddress: string | null;
  pricesIncludeTax: boolean;
};

export async function saveTaxProfile(input: ProfileInput): Promise<Result<TaxSetup>> {
  return attempt(async () => {
    const setup = await api.put<TaxSetup>("/tax/profile", input);
    refresh();
    return setup;
  });
}

export async function addTaxRate(input: { code: string; rateBp: number; validFrom: string; basis: string }): Promise<Result<TaxSetup>> {
  return attempt(async () => {
    const setup = await api.post<TaxSetup>("/tax/rates", input);
    refresh();
    return setup;
  });
}

export async function computeSale(input: SaleInput): Promise<Result<ComputedSale>> {
  return attempt(() => api.post<ComputedSale>("/tax/compute", input));
}
