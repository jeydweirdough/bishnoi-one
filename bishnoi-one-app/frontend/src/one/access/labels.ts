import { moduleByAppKey } from "@/src/platform/lib/modules";
import type { AccessModule } from "./types";

/** A module as this site names it (CRM, Inventory), not its full name on the Platform ("Bishnoi One CRM"). */
export const moduleLabel = (m: Pick<AccessModule, "key" | "name">): string => moduleByAppKey(m.key)?.label ?? m.name;
