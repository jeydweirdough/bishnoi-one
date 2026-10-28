import { TIMING_OPTIONS } from "@/src/platform/ui/document-header";
import { FilterSelect } from "./ui";

// The lists' filters for the document header (feature plan step 8): by operation type and by timing,
// inside each list's filter bar (its Show button sends them).

export type OperationTypeRow = { id: string; code: string; name: string; kind: string; warehouseId: string | null; isDefault: boolean; isActive: boolean };

export function HeaderFilters({ types, kinds, operationType, timing }: { types: OperationTypeRow[]; kinds: string[]; operationType: string; timing: string }) {
  const mine = types.filter((t) => kinds.includes(t.kind) && (t.isActive || t.id === operationType));
  return (
    <>
      {mine.length > 1 && (
        <FilterSelect name="operationType" value={operationType} label="Operation" options={[{ value: "", label: "Every operation" }, ...mine.map((t) => ({ value: t.id, label: t.name }))]} />
      )}
      <FilterSelect name="timing" value={timing} label="Timing" options={TIMING_OPTIONS} />
    </>
  );
}
