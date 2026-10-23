// Inventory's screens were written for an app that was Inventory and nothing
// else. In the one app (decided 2026-10-23) it still is "this app", but its pages
// are under /inventory and every other module is at its own path: this says so, in
// the shape the module's kit asks for. Written by scripts/move-module.mjs.
export * from "@/src/platform/lib/apps";
import { appOf, type AppName } from "@/src/platform/lib/apps";
import { moduleByAppKey } from "@/src/platform/lib/modules";

export const THIS_APP: AppName | "" = "inventory";

/** An app's screens in the one app: its module's path. */
export const appUrl = (app: AppName): string => moduleByAppKey(app)?.path ?? `/${app}`;

/** Every module has an address here. */
export const addressKnown = (_app: AppName): boolean => true;

/** A screen of another app: under its module's path. This module's own links are already /inventory/... */
export function href(app: AppName, path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  return app === THIS_APP ? clean : `${appUrl(app)}${clean}`;
}

export const leaves = (app: AppName): boolean => app !== THIS_APP;
export const isOurs = (app: AppName): boolean => app === THIS_APP;

/** Where a module's screens sit: this module's at /inventory, any other at its path. */
export const moduleBase = (key: string): string => {
  const app = appOf(key);
  return app ? appUrl(app) : `/${key}`;
};

export const platformHome = (): string => "/platform";
export const thisAppLabel = (): string | null => "Inventory";
export const canUseThisApp = (_me: unknown): boolean => true;
export const setAddresses = (_map: unknown): void => undefined;
