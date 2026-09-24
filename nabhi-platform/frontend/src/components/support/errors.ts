// The API names a field either way (companyId from validation, company_id from
// its own checks); a form asks for it once.
export function fieldError(fields: Record<string, string> | undefined, name: string): string | undefined {
  if (!fields) return undefined;
  const snake = name.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
  return fields[name] ?? fields[snake];
}

/** A field's text as the API wants it: trimmed, and nothing when empty. */
export const orNull = (v: string) => v.trim() || null;
