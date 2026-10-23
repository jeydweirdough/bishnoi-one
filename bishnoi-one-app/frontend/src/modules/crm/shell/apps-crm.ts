// The CRM's sidebar (./nav.tsx) was written for an app that is the CRM and
// nothing else. In the one app (decided 2026-10-23) it still is "the CRM", but
// its pages are under /crm and every other module is at its own path here: this
// says so, in the shape nav.tsx asks for (the kit's lib/apps.ts).
import { appLabel, appOf, type AppName } from "@/src/platform/lib/apps";
import { moduleByAppKey } from "@/src/platform/lib/modules";

export { appLabel, appOf };

export const THIS_APP: AppName = "crm";

/** An app's screens in the one app: its module's path (the CRM's is /crm). */
export const appUrl = (app: AppName): string => moduleByAppKey(app)?.path ?? `/${app}`;

/** A screen of another app: under its module's path. The CRM's own links are already /crm/... */
export function href(app: AppName, path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  return app === "crm" ? clean : `${appUrl(app)}${clean}`;
}

export const isOurs = (app: AppName): boolean => app === "crm";

/** Where a module's screens sit: the CRM's at /crm, any other at its path. */
export const moduleBase = (key: string): string => {
  const app = appOf(key);
  return app ? appUrl(app) : `/${key}`;
};

export const platformHome = (): string => "/platform";

export const thisAppLabel = (): string => "CRM";
