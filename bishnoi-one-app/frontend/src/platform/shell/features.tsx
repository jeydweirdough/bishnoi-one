"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { Features } from "@/src/platform/lib/features";

// The company's catalogue switches (step 6), given once by the signed-in layout to every screen.
const FeaturesContext = createContext<Features | null>(null);

/** A company an operator can work in: the sidebar's company switcher lists them (operators only, decided 2026-10-29). */
export type SwitchCompany = { slug: string; name: string; current: boolean };
const CompaniesContext = createContext<SwitchCompany[] | null>(null);

export function FeaturesProvider({ features, companies = null, children }: { features: Features | null; companies?: SwitchCompany[] | null; children: ReactNode }) {
  return (
    <FeaturesContext.Provider value={features}>
      <CompaniesContext.Provider value={companies}>{children}</CompaniesContext.Provider>
    </FeaturesContext.Provider>
  );
}

/** The companies an operator can switch to; null for everyone else (one email, one company). */
export function useOperatorCompanies(): SwitchCompany[] | null {
  return useContext(CompaniesContext);
}

export function useFeatures(): Features | null {
  return useContext(FeaturesContext);
}
