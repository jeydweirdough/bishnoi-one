"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { Features } from "@/src/platform/lib/features";

// The company's catalogue switches (step 6), given once by the signed-in layout to every screen.
const FeaturesContext = createContext<Features | null>(null);

export function FeaturesProvider({ features, children }: { features: Features | null; children: ReactNode }) {
  return <FeaturesContext.Provider value={features}>{children}</FeaturesContext.Provider>;
}

export function useFeatures(): Features | null {
  return useContext(FeaturesContext);
}
