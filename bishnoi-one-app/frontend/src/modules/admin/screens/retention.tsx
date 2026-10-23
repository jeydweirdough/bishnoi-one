import { managersOnly } from "@/src/modules/admin/components/gate";
import { RetentionRulesEditor } from "@/src/modules/admin/components/retention-rules";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { load } from "@/src/modules/admin/platform/lib/api";
import type { RetentionRuleRow } from "@/src/modules/admin/platform/lib/types";

export const metadata = { title: "Retention rules" };

export default async function RetentionRulesPage() {
  const stop = await managersOnly();
  if (stop) return stop;
  const { divisions } = await load<{ divisions: RetentionRuleRow[] }>("/admin/retention");
  return (
    <>
      <PageHeader title="Retention rules">
        When a division&apos;s customers count as at risk, then lost, with no quote. Who sees team and per-rep figures is the
        Reports column in Roles &amp; permissions.
      </PageHeader>
      {/* Keyed on the saved values so a save starts the form from what's stored. */}
      <RetentionRulesEditor key={JSON.stringify(divisions)} rows={divisions} />
    </>
  );
}
