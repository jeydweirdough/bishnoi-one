"use client";

import { createContext, useContext, type ReactNode } from "react";
import { GENERAL_TERMS, type Terms } from "./terms";

// The company's own words, for the parts drawn in the browser. Server screens
// use termsOf(me) directly.
const Words = createContext<Terms>(GENERAL_TERMS);

export function TermsProvider({ terms, children }: { terms: Terms; children: ReactNode }) {
  return <Words.Provider value={terms}>{children}</Words.Provider>;
}

export const useTerms = () => useContext(Words);
