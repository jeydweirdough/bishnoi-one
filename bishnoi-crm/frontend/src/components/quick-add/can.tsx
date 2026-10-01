"use client";

import { createContext, useContext, type ReactNode } from "react";

// What the signed-in person may do, for the parts of a form that offer to
// make what's missing (a "+ Add" beside a field). The API checks again on
// every call; this only decides what's offered.

const Permissions = createContext<readonly string[]>([]);

export function CanProvider({ permissions, children }: { permissions: readonly string[]; children: ReactNode }) {
  return <Permissions.Provider value={permissions}>{children}</Permissions.Provider>;
}

export function useCan(): (permission: string) => boolean {
  const permissions = useContext(Permissions);
  return (permission) => permissions.includes(permission);
}

// Which form (Settings → Forms) the fields inside belong to: a pick-list's
// "+ Add a choice" adds to that form's list.
const Entity = createContext<"company" | "contact" | "product" | "quote" | null>(null);

export function FormEntityProvider({ entity, children }: { entity: "company" | "contact" | "product" | "quote"; children: ReactNode }) {
  return <Entity.Provider value={entity}>{children}</Entity.Provider>;
}

export const useFormEntity = () => useContext(Entity);
