// Settings: how the platform runs, in four sections. Everyone sees them; a
// Platform Admin changes them, one section at a time.
import { PageHeader } from "@/src/modules/console/platform/ui/sheet";
import { load } from "@/src/modules/console/platform/lib/api";
import { getStaff } from "@/src/modules/console/components/gate";
import { Tabs } from "@/src/modules/console/components/marks";
import { MonitoringForm, NotificationsForm, PlatformForm, SecurityForm } from "@/src/modules/console/components/settings/settings-forms";
import type { PlatformSettings } from "@/src/modules/console/lib/types";

export const metadata = { title: "Settings" };

type Search = Promise<Record<string, string | string[] | undefined>>;

const TABS = [
  { key: "platform", label: "Platform" },
  { key: "monitoring", label: "Applications and monitoring" },
  { key: "notifications", label: "Notifications" },
  { key: "security", label: "Security" },
] as const;

export default async function Page({ searchParams }: { searchParams: Search }) {
  const { tab: asked } = await searchParams;
  const tab = TABS.find((t) => t.key === asked)?.key ?? "platform";
  const [{ settings }, staff] = await Promise.all([load<{ settings: PlatformSettings }>("/platform/settings"), getStaff()]);
  const readOnly = !staff.canAdminister;

  return (
    <>
      <PageHeader title="Settings">How the platform runs. Each section saves separately and takes effect immediately.</PageHeader>

      <Tabs tabs={TABS.map((t) => ({ key: t.key, label: t.label, href: t.key === "platform" ? "/platform/console/settings" : `/platform/console/settings?tab=${t.key}` }))} current={tab} />

      {readOnly && (
        <p className="mb-4 text-meta text-ink-3">Read only. Only a Platform Admin can change settings.</p>
      )}

      <div className="max-w-[44rem]">
        {tab === "platform" && <PlatformForm initial={settings.platform} readOnly={readOnly} />}
        {tab === "monitoring" && <MonitoringForm initial={settings.monitoring} readOnly={readOnly} />}
        {tab === "notifications" && <NotificationsForm initial={settings.notifications} readOnly={readOnly} />}
        {tab === "security" && <SecurityForm initial={settings.security} readOnly={readOnly} />}
      </div>
    </>
  );
}
