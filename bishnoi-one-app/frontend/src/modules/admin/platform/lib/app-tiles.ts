import { Building2, HeartPulse, Landmark, Network, Package, Users, type LucideIcon } from "lucide-react";
import type { AppName } from "@/src/modules/admin/platform/lib/apps";

// The Bishnoi One apps as tiles: one list for the app launcher in every app's
// top bar (shell/app-launcher.tsx) and for the Bishnoi One sign-in page. The
// icons are stand-ins until each app has its own mark: change them here.
//
// Same file in every app's src/platform/lib/: copy it as it is.

export type AppTile = { app: AppName; icon: LucideIcon; tint: string; ink: string; blurb: string };

/** The apps with screens, in the order people reach for them. Regulatory and In-Licensing have no screens yet. */
export const APP_TILES: AppTile[] = [
  { app: "crm", icon: Users, tint: "#e9f0fb", ink: "#4c78c8", blurb: "Customers and sales" },
  { app: "inventory", icon: Package, tint: "#e7f1ea", ink: "#3f5e4a", blurb: "Stock and orders" },
  { app: "finance", icon: Landmark, tint: "#fcf3dd", ink: "#9a6a12", blurb: "Invoices and tax" },
  { app: "pharmacy", icon: HeartPulse, tint: "#fbe7e3", ink: "#c2493a", blurb: "Prescriptions" },
  { app: "exec", icon: Building2, tint: "#efeafb", ink: "#7a5cc4", blurb: "Company settings" },
  { app: "platform", icon: Network, tint: "#fdeedf", ink: "#b75a10", blurb: "Companies and access" },
];

export const tileOf = (app: string): AppTile | undefined => APP_TILES.find((t) => t.app === app);
