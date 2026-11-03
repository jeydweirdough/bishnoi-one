"use client";

import { Input } from "@/src/platform/ui/field";

/**
 * A work email at the company's domain (2026-11-01): you type the name, the field already has @getmeds.ph. `value`
 * and `onChange` are the whole email, so forms stay as they were. Pasting a whole email keeps the part before the @.
 * With no domain set, an ordinary email field.
 */
export function WorkEmailInput({ domain, value, onChange, ...field }: { domain?: string | null; value: string; onChange: (email: string) => void; id: string; "aria-invalid"?: boolean; "aria-describedby"?: string; autoFocus?: boolean }) {
  if (!domain) return <Input {...field} type="email" value={value} onChange={(e) => onChange(e.target.value)} maxLength={254} />;
  const at = `@${domain}`;
  return (
    <Input
      {...field}
      autoComplete="off"
      spellCheck={false}
      placeholder="name"
      suffix={<span className="text-ink-3">{at}</span>}
      value={value.split("@")[0]}
      onChange={(e) => {
        const name = e.target.value.split("@")[0].replace(/\s/g, "").toLowerCase();
        onChange(name ? `${name}${at}` : "");
      }}
      maxLength={64}
    />
  );
}
