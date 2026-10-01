"use client";

import type { FormFieldDef } from "@/src/platform/lib/types";
import { useCan, useFormEntity } from "./can";
import { AddChoice } from "./forms";
import { QuickAdd } from "./quick-add";

/** "+ Add a choice" under a pick-list, for an admin who keeps the forms. */
export function ChoiceAdd({ field, onAdded }: { field: FormFieldDef; onAdded: (option: string) => void }) {
  const can = useCan();
  const entity = useFormEntity();
  if (!entity || !can("admin.settings")) return null;
  return (
    <QuickAdd label="Add a choice" title={`Add to ${field.label}`}>
      {(done) => <AddChoice entity={entity} fieldKey={field.key} fieldLabel={field.label} onAdded={onAdded} done={done} />}
    </QuickAdd>
  );
}
