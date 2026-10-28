"use client";

import { Field, Input, Select } from "@/src/modules/inventory/platform/ui/field";
import type { OperationTypeRow } from "./document-header";

// The document header's fields on a stock form (feature plan step 8): the operation type, the date it
// is scheduled for, and the document it comes from. Whoever makes it is responsible until changed.

export type HeaderValue = { operationTypeId: string; scheduledOn: string; sourceDocument: string };

export function headerValue(header?: { operationType: { id: string } | null; scheduledOn: string | null; sourceDocument: string | null } | null): HeaderValue {
  return { operationTypeId: header?.operationType?.id ?? "", scheduledOn: header?.scheduledOn ?? "", sourceDocument: header?.sourceDocument ?? "" };
}

/** What the form sends: only what was filled in (the rest gets its default). */
export function headerOut(v: HeaderValue, withDate = true): Record<string, string | null> {
  return {
    ...(v.operationTypeId ? { operationTypeId: v.operationTypeId } : {}),
    ...(withDate ? { scheduledOn: v.scheduledOn || null } : {}),
    sourceDocument: v.sourceDocument.trim() || null,
  };
}

export function HeaderFields({ types, kinds, value, onChange, errors, withDate = true }: {
  types: OperationTypeRow[];
  kinds: string[];
  value: HeaderValue;
  onChange: (v: HeaderValue) => void;
  errors: Record<string, string | undefined>;
  /** Off where the form has its own date for it (an order's required date). */
  withDate?: boolean;
}) {
  const mine = types.filter((t) => kinds.includes(t.kind) && (t.isActive || t.id === value.operationTypeId));
  const fallback = mine.find((t) => t.isDefault && t.kind === kinds[0]);
  return (
    <>
      {mine.length > 1 && (
        <Field label="Operation" error={errors.operationTypeId}>
          {(p) => (
            <Select {...p} value={value.operationTypeId || fallback?.id || ""} onChange={(e) => onChange({ ...value, operationTypeId: e.target.value })}>
              {mine.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      {withDate && (
        <Field label="Scheduled date" optional error={errors.scheduledOn}>
          {(p) => <Input {...p} type="date" value={value.scheduledOn} onChange={(e) => onChange({ ...value, scheduledOn: e.target.value })} />}
        </Field>
      )}
      <Field label="Source document" optional hint="The document it comes from, such as a customer's PO number." error={errors.sourceDocument}>
        {(p) => <Input {...p} value={value.sourceDocument} maxLength={80} onChange={(e) => onChange({ ...value, sourceDocument: e.target.value })} />}
      </Field>
    </>
  );
}
