"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { OneMenu } from "./one-menu";

// The one menu (src/one/menu/one-menu.ts), built once per request by the signed-in layout and
// drawn by the shared sidebar on every page, whichever module keeps the page.
const MenuContext = createContext<OneMenu | null>(null);

export function OneMenuProvider({ menu, children }: { menu: OneMenu; children: ReactNode }) {
  return <MenuContext.Provider value={menu}>{children}</MenuContext.Provider>;
}

export function useOneMenu(): OneMenu | null {
  return useContext(MenuContext);
}
