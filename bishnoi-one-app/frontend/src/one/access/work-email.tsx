"use client";

import { Input } from "@/src/platform/ui/field";

/**
 * The email an employee signs in with: any address (Gmail too). The company-email-domain behaviour (typing only
 * the name before a fixed @domain) was removed on 2026-11-17 with the one-domain-per-company rule.
 */
export function WorkEmailInput({ value, onChange, ...field }: { value: string; onChange: (email: string) => void; id: string; "aria-invalid"?: boolean; "aria-describedby"?: string; autoFocus?: boolean }) {
  return <Input {...field} type="email" value={value} onChange={(e) => onChange(e.target.value)} maxLength={254} />;
}
