import { ExternalLink } from "lucide-react";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { Pill } from "@/src/platform/ui/figures";
import { can } from "@/src/platform/lib/access";
import { appUrl } from "@/src/platform/lib/apps";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import type { Connections } from "../actions/settings";

export const metadata = { title: "Connections" };

/**
 * Which outside services the CRM can use for this company. They're connected
 * on Bishnoi One Platform (Companies → the company → Connections), so nothing
 * about them is kept on the CRM's server: this says which are on, and where to change them.
 */
export default async function ConnectionsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="Settings" />;
  const page = await load<Connections>("/admin/connections");
  const onPlatform = `${appUrl("platform")}/companies?q=${encodeURIComponent(page.company ?? "")}`;
  return (
    <>
      <PageHeader title="Settings">The outside services the CRM uses. They&apos;re connected for your company on Bishnoi One Platform.</PageHeader>
      <div className="max-w-3xl space-y-4">
        <Sheet className="px-5 py-4 sm:px-6">
          {page.connected ? (
            <p className="text-sm text-ink-2">
              To connect one, or change its details, a Bishnoi One administrator opens your company on the Platform, then its Connections tab. The CRM picks the
              change up within 5 minutes.
            </p>
          ) : (
            <p className="text-sm text-ink-2">
              The CRM isn&apos;t connected to Bishnoi One Platform yet, so it can&apos;t use any of these. Your Bishnoi One administrator makes the CRM&apos;s connect key
              on the Platform (Connections) and puts it on the CRM&apos;s server as PLATFORM_APP_KEY.
            </p>
          )}
          <a href={onPlatform} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-ink underline-offset-2 hover:underline">
            Open your company on Bishnoi One Platform <ExternalLink className="size-3.5" aria-hidden />
          </a>
        </Sheet>
        <Sheet>
          <ul className="divide-y divide-rule">
            {page.services.map((s) => (
              <li key={s.key} className="flex items-start justify-between gap-4 px-5 py-4 sm:px-6">
                <span className="min-w-0">
                  <span className="block font-semibold text-ink">{s.name}</span>
                  <span className="block text-sm text-ink-2">{s.purpose}</span>
                </span>
                <Pill tone={s.on ? "good" : "plain"} className="shrink-0">
                  {s.on ? "Connected" : "Not connected"}
                </Pill>
              </li>
            ))}
          </ul>
        </Sheet>
      </div>
    </>
  );
}
