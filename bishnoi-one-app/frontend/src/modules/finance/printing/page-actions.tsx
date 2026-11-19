"use client";

import { createContext, useContext, type ReactNode } from "react";
import { FinancePrintButton } from "./print-action";

// Eligibility stays with FinancePrintFrame; headers only arrange its action.
export const FinancePagePrintContext = createContext(false);

export function FinancePageActions({ children }: { children?: ReactNode }) {
  const printable = useContext(FinancePagePrintContext);
  if (!printable && !children) return null;

  return <div className="finance-page-actions">
    {printable && <span data-finance-page-print><FinancePrintButton label="Print / Save as PDF" /></span>}
    {children}
  </div>;
}
