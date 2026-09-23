import Link from "next/link";
import { can } from "@/src/platform/lib/access";
import type { Me } from "@/src/platform/lib/types";

/** Everything an admin sets up for everyone, one tab each. A tab shows only to a role that may open it. */
export const SETTINGS_TABS = [
  { href: "/admin/settings", label: "Forms", permission: "admin.settings" },
  { href: "/admin/settings/company", label: "Business & quotes", permission: "admin.settings" },
  { href: "/admin/settings/customer-types", label: "Customer types", permission: "admin.types" },
  { href: "/admin/settings/pricing", label: "Pricing & retention", permission: "products.view" },
] as const;

export type SettingsTab = (typeof SETTINGS_TABS)[number]["href"];

export const settingsTabsFor = (me: Me) => SETTINGS_TABS.filter((t) => can(me, t.permission));

export function SettingsTabs({ me, current }: { me: Me; current: SettingsTab }) {
  return (
    <nav aria-label="Settings" className="mb-5 flex flex-wrap gap-x-6 gap-y-1 border-b border-rule">
      {settingsTabsFor(me).map((t) => (
        <Link
          key={t.href}
          href={t.href}
          aria-current={t.href === current ? "page" : undefined}
          className={`-mb-px border-b-2 px-1 pb-2 text-sm ${
            t.href === current ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"
          }`}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
