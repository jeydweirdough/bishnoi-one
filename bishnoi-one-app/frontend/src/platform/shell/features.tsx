"use client";

import { createContext, useContext, type ReactNode } from "react";

// Given once by the signed-in layout to every screen. (The company's app catalogue switches that
// hid pages were removed on 2026-11-17, owner's decision; only the operators' companies remain.)

/** A company an operator can work in: the sidebar's company switcher lists them (operators only, decided 2026-10-29). */
export type SwitchCompany = { slug: string; name: string; current: boolean };
const CompaniesContext = createContext<SwitchCompany[] | null>(null);

export function FeaturesProvider({ companies = null, children }: { companies?: SwitchCompany[] | null; children: ReactNode }) {
  return <CompaniesContext.Provider value={companies}>{children}</CompaniesContext.Provider>;
}

/** The companies an operator can switch to; null for everyone else (one email, one company). */
export function useOperatorCompanies(): SwitchCompany[] | null {
  return useContext(CompaniesContext);
}
