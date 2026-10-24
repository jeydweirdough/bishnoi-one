"use client";

import type { FormFieldDef } from "@/src/platform/lib/types";
import { useCan, useFormEntity } from "@/src/modules/crm/components/quick-add/can";
import { AddChoice } from "@/src/modules/crm/components/quick-add/forms";
import { QuickAdd } from "@/src/modules/crm/components/quick-add/quick-add";

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
