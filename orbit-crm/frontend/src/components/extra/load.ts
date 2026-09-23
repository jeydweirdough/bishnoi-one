import "server-only";
import { load } from "@/src/platform/lib/api";
import type { CustomEntity, FormFieldDef, FormLayout } from "@/src/platform/lib/types";

/** A record's form as people fill it in (Settings → Forms): sections, and the fields shown in each. */
export const formLayout = (entity: CustomEntity) => load<FormLayout>(`/forms/${entity}`);

/** Every field on the form, in order. */
export const layoutFields = (layout: FormLayout): FormFieldDef[] => layout.sections.flatMap((s) => s.fields);

/** The fields an admin added (their values live in the record's `extra`). */
export async function customFields(entity: CustomEntity): Promise<FormFieldDef[]> {
  return layoutFields(await formLayout(entity)).filter((f) => !f.standard);
}
