import type { ReactNode } from "react";
import { Brand } from "./brand";
import { OneActions } from "./one-actions";

/**
 * A page with no module sidebar (a module not built yet, a module that couldn't
 * be opened): the brand at the top left, your modules and account at the top
 * right, where a module's pages have them.
 */
export function PlainFrame({ children }: { children: ReactNode }) {
  return (
    <>
      <div className="mx-auto flex h-16 max-w-[90rem] items-center justify-between gap-4 px-4 sm:px-6">
        <Brand />
        <div className="flex items-center gap-1">
          <OneActions />
        </div>
      </div>
      {children}
    </>
  );
}
