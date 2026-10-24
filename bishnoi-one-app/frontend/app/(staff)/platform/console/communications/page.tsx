// Communications: what the platform tells people. Announcements, system
// notifications and maintenance notices, each for everyone, one company, or
// one application's users, shown by the applications while they run.
import { PageHeader } from "@/src/modules/console/platform/ui/sheet";
import { load } from "@/src/modules/console/platform/lib/api";
import { getStaff } from "@/src/modules/console/components/gate";
import { Tabs } from "@/src/modules/console/components/marks";
import { NoticeBoard } from "@/src/modules/console/components/communications/notice-board";
import { NOTICE_KINDS } from "@/src/modules/console/lib/words";
import type { Notice, NoticeKind, Options } from "@/src/modules/console/lib/types";

export const metadata = { title: "Communications" };

type Search = Promise<Record<string, string | string[] | undefined>>;

const KINDS = Object.keys(NOTICE_KINDS) as NoticeKind[];

export default async function Page({ searchParams }: { searchParams: Search }) {
  const { kind: asked } = await searchParams;
  const kind = KINDS.find((k) => k === asked) ?? "announcement";
  const [{ notices }, options, staff] = await Promise.all([
    load<{ notices: Notice[] }>(`/platform/announcements?kind=${kind}`),
    load<Options>("/platform/options"),
    getStaff(),
  ]);

  return (
    <>
      <PageHeader title="Communications">
        What the platform tells the people using it. The applications show whatever is showing by asking{" "}
        <code className="rounded-md bg-bench px-1 text-meta">/public/notices?app=&lt;key&gt;&amp;company=&lt;slug&gt;</code>, so a notice
        reaches exactly the people it&apos;s for.
      </PageHeader>

      <Tabs
        tabs={KINDS.map((k) => ({ key: k, label: NOTICE_KINDS[k].many, href: k === "announcement" ? "/platform/console/communications" : `/platform/console/communications?kind=${k}` }))}
        current={kind}
      />

      <NoticeBoard
        key={kind}
        kind={kind}
        notices={notices}
        companies={options.companies}
        applications={options.applications}
        canAdminister={staff.canAdminister}
      />
    </>
  );
}
