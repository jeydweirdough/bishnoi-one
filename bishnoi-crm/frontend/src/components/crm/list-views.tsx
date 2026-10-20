import { Later } from "@/src/platform/ui/later";
import { load } from "@/src/platform/lib/api";
import type { ViewList, Views } from "@/src/actions/views";
import { ViewsBar } from "./views-bar";

const NONE: Views = { items: [], canShare: false };

/** A list's saved views above its filters: "All" at once, the views as they arrive. */
export function ListViews({ list }: { list: ViewList }) {
  const views = load<Views>(`/views?list=${list}`).catch(() => NONE);
  return (
    <Later data={views} fallback={<ViewsBar list={list} views={NONE} />}>
      {(v) => <ViewsBar list={list} views={v} />}
    </Later>
  );
}
