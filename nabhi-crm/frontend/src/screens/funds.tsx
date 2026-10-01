import { Plus } from "lucide-react";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { LinkButton } from "@/src/platform/ui/button";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { Filters } from "../components/crm/list-controls";
import { FundList } from "../components/funds/fund-list";
import type { FundRequest } from "../components/funds/types";

// Marketing requests, three ways: your own, the ones waiting on your decision,
// and everyone's within your reach (a Team Lead's team).

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
type Answer = { items: FundRequest[]; financeError: string | null };

const STATES = [
  { value: "", label: "Open" },
  { value: "done", label: "Closed" },
  { value: "any", label: "All" },
];

function FinanceNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p className="mb-3 rounded-[3px] bg-danger-tint px-3 py-2 text-meta text-danger">Finance couldn&apos;t be asked just now ({error}). What&apos;s shown is its last answer.</p>;
}

function AskButton({ primary = false }: { primary?: boolean }) {
  return (
    <LinkButton href="/funds/new" variant={primary ? "primary" : "default"} icon={<Plus className="size-4" aria-hidden />}>
      New marketing request
    </LinkButton>
  );
}

export const metadata = { title: "Marketing requests" };

/** Your own requests. */
export default async function MyFunds({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "funds.view")) return <NoAccess what="marketing requests" />;
  const sp = await searchParams;
  const state = one(sp.state) || "open";
  const q = one(sp.q);
  const list = await load<Answer>(`/funds?show=mine&state=${enc(state)}${q ? `&q=${enc(q)}` : ""}`);
  const fmt = makeFormat(me.org);
  const mayAsk = can(me, "funds.create");
  return (
    <>
      <PageHeader title="My marketing requests" actions={mayAsk && <AskButton primary />}>
        Cash advances for business expenses such as client meals and transportation. Approved by your Team Lead, released by Finance, and liquidated with
        official receipts.
      </PageHeader>
      <Filters search="Number, purpose or details" selects={[{ name: "state", label: "Showing", options: STATES }]} />
      <FinanceNote error={list.financeError} />
      <Sheet className="mt-4">
        {list.items.length === 0 ? (
          <Empty title={state === "open" ? "Nothing open" : "No requests here"} icon="payments" actions={mayAsk && state === "open" && <AskButton primary />}>
            {state === "open" ? "Submit a request before incurring the expense, and track it here until it is settled." : "Nothing matches."}
          </Empty>
        ) : (
          <FundList items={list.items} fmt={fmt} showWho={false} />
        )}
      </Sheet>
    </>
  );
}

/** What's waiting on this person's decision: their team's requests, oldest first. */
export async function FundsToApprove() {
  const me = await getCompanyMe();
  if (!can(me, "funds.approve")) return <NoAccess what="approving marketing requests" />;
  const list = await load<Answer>("/funds?show=approve");
  const fmt = makeFormat(me.org);
  return (
    <>
      <PageHeader title="For approval">Your team's requests, oldest first. Approved requests are forwarded to Finance for release.</PageHeader>
      <Sheet>
        {list.items.length === 0 ? (
          <Empty title="No requests for approval" icon="approvals">
            Your team&apos;s requests appear here once submitted.
          </Empty>
        ) : (
          <FundList items={list.items} fmt={fmt} showWho />
        )}
      </Sheet>
    </>
  );
}

/** Everyone's within reach: a Team Lead's team, an Administrator's company. */
export async function TeamFunds({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "funds.approve")) return <NoAccess what="the team's marketing requests" />;
  const sp = await searchParams;
  const state = one(sp.state) || "open";
  const q = one(sp.q);
  const list = await load<Answer>(`/funds?show=all&state=${enc(state)}${q ? `&q=${enc(q)}` : ""}`);
  const fmt = makeFormat(me.org);
  const total = list.items.reduce((sum, r) => sum + (r.approvedCentavos ?? 0), 0);
  return (
    <>
      <PageHeader title={me.role?.scope === "all" ? "All requests" : "Team requests"}>
        {list.items.length} {list.items.length === 1 ? "request" : "requests"}
        {total > 0 && ` · ${fmt.peso(total)} approved`}
      </PageHeader>
      <Filters search="Number, person, purpose or details" selects={[{ name: "state", label: "Showing", options: STATES }]} />
      <FinanceNote error={list.financeError} />
      <Sheet className="mt-4">
        {list.items.length === 0 ? (
          <Empty title="No requests here" icon="payments">
            Nothing matches.
          </Empty>
        ) : (
          <FundList items={list.items} fmt={fmt} showWho />
        )}
      </Sheet>
    </>
  );
}
