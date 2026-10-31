import type { ReactNode } from "react";
import { apiFor, ApiError } from "@/src/platform/lib/api";
import type { ModuleKey } from "@/src/platform/lib/modules";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import type { BinItem, CleanupKind } from "./actions";
import { CleanupBoard } from "./board";

/** Data clean-up and the recycle bin for one app (2026-10-30): its administrators only (the app checks).
 *  `tabs`: drawn under the title (the Admin Console's choice of app, 2026-10-31). */
export async function DataCleanupPage({ module, path, tabs }: { module: ModuleKey; path: string; tabs?: ReactNode }) {
  let kinds: { kinds: CleanupKind[]; days: number };
  let bin: { items: BinItem[] };
  try {
    [kinds, bin] = await Promise.all([apiFor(module).get<{ kinds: CleanupKind[]; days: number }>("/data-cleanup/kinds"), apiFor(module).get<{ items: BinItem[] }>("/data-cleanup/bin")]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return (
        <>
          <PageHeader title="Data clean-up" />
          {tabs}
          <Sheet>
            <Empty icon="lists" title="For administrators">
              Only administrators delete records and use the recycle bin. Ask your company&apos;s administrator.
            </Empty>
          </Sheet>
        </>
      );
    }
    throw error;
  }
  return (
    <>
      <PageHeader title="Data clean-up">Delete records you don&apos;t need, with what belongs only to them. They wait in the recycle bin for {kinds.days} days, restorable, then are erased.</PageHeader>
      {tabs}
      <CleanupBoard module={module} path={path} kinds={kinds.kinds} bin={bin.items} days={kinds.days} />
    </>
  );
}
