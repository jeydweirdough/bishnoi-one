import { ExternalLink, Plus, Printer } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { FigureStrip, ListFrame, ListToolbar, StatusPill, UnderlineTabs, type PillTone } from "@/src/platform/ui/list-layout";
import { ExpandableTable } from "@/src/platform/ui/expandable-table";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat, type Format } from "@/src/modules/finance/platform/lib/format";
import { PrintButton } from "@/src/modules/finance/invoices/steps";
import { PrintAttachmentSources } from "@/src/modules/finance/printing/attachment-source";
import { SignatureLines } from "@/src/modules/finance/signature/blocks";
import type { SignedStep } from "@/src/modules/finance/signature/types";
import { PettyCashEditor } from "@/src/modules/finance/petty-cash/editor";
import { ReceiptPreview } from "@/src/modules/finance/petty-cash/receipt-preview";
import { ReceiptSlot } from "@/src/modules/finance/petty-cash/receipt-slot";
import { DeletePettyCash, PettyCashSteps, VoidPettyCash } from "@/src/modules/finance/petty-cash/steps";
import type { BillFile } from "@/src/modules/finance/payables/types";
import type { PettyCashChoices, PettyCashList, PettyCashShow, PettyCashStatus, PettyCashVoucher } from "@/src/modules/finance/petty-cash/types";

// Petty cash (app/routers/petty_cash.py; decided 2026-10-30, Plans/Plan - Petty cash and receipts):
// one voucher per paper petty cash voucher, a line for each official receipt with its photo or
// PDF. Whoever makes vouchers (petty_cash.create) enters and submits it; someone who may check
// (petty_cash.check), never whoever made or submitted it, checks it against its receipts and
// posts it, or returns it with the reason. A posted one is voided with a reason (petty_cash.void).

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const PAGE = "/finance/petty-cash";

const TONE: Record<PettyCashStatus, PillTone> = { draft: "plain", to_check: "info", returned: "warn", posted: "good", void: "bad" };

/** Each tab: its list, the line saying what it is and who acts next, and the permission that acts on it. */
const TABS: { key: PettyCashShow; label: string; says: string; acts: "create" | "check" | "void" | null; empty: string }[] = [
  {
    key: "to_check",
    label: "To check",
    says: "Submitted vouchers waiting to be checked against their receipts. Next: someone whose role may check petty cash opens each receipt beside its line, then checks and posts it, or returns it with the reason. Whoever made or submitted a voucher doesn't check it.",
    acts: "check",
    empty: "No vouchers waiting to be checked.",
  },
  {
    key: "returned",
    label: "Returned",
    says: "Vouchers sent back with a reason. Next: whoever made it corrects it and submits it again.",
    acts: "create",
    empty: "No returned vouchers.",
  },
  {
    key: "draft",
    label: "Drafts",
    says: "Vouchers being entered. Next: whoever made it attaches a photo or PDF of every receipt, then submits it for checking.",
    acts: "create",
    empty: "No drafts.",
  },
  {
    key: "posted",
    label: "Posted",
    says: "Checked and posted to the books on the voucher's date, and in the BIR purchase lists. Nothing more to do; a mistake is voided with a reason.",
    acts: null,
    empty: "No posted vouchers yet.",
  },
  {
    key: "void",
    label: "Void",
    says: "Voided vouchers: their entry was reversed on the day they were voided. Kept, with their receipts and history, for the record.",
    acts: null,
    empty: "No voided vouchers.",
  },
  { key: "all", label: "All", says: "Every petty cash voucher, newest first.", acts: null, empty: "No petty cash vouchers yet." },
];

const isShow = (v: unknown): v is PettyCashShow => TABS.some((t) => t.key === v);

const EVENT_LABELS: Record<string, string> = {
  submitted: "Submitted for checking",
  resubmitted: "Corrected and submitted again",
  posted: "Checked and posted to the books",
  returned: "Returned for correction",
  voided: "Voided",
};

function StatusMark({ status, label }: { status: PettyCashStatus; label: string }) {
  return <StatusPill tone={TONE[status]}>{label}</StatusPill>;
}

function Receipts({ n, missing }: { n: number; missing: number }) {
  return (
    <>
      <span className="tabular-nums">{n === 1 ? "1 receipt" : `${n} receipts`}</span>
      {missing > 0 && <span className="block text-meta font-semibold text-due-today">{missing === 1 ? "1 receipt missing" : `${missing} receipts missing`}</span>}
    </>
  );
}

export async function PettyCashPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const q = one(sp.q).trim().slice(0, 100);
  const asked = isShow(sp.show) ? sp.show : null;
  const listOf = (show: PettyCashShow) => {
    const query = new URLSearchParams({ show });
    if (q) query.set("q", q);
    return load<PettyCashList>(`/finance/petty-cash?${query}`);
  };

  // No tab asked: open where something waits for this person. "Waiting for you" (the API's) is the
  // vouchers you may check plus your own returned ones; those to check are the ones you may check.
  let show: PettyCashShow;
  let list: PettyCashList;
  if (asked) {
    show = asked;
    list = await listOf(asked);
  } else {
    const toCheck = await listOf("to_check");
    const mineToCheck = toCheck.items.filter((x) => x.canCheck).length;
    const mineReturned = toCheck.waitingForYou - mineToCheck;
    show = toCheck.may.check && mineToCheck > 0 ? "to_check" : mineReturned > 0 ? "returned" : toCheck.may.create ? "draft" : "posted";
    list = show === "to_check" ? toCheck : await listOf(show);
  }
  const tab = TABS.find((t) => t.key === show)!;
  const yours = tab.acts && list.may[tab.acts];

  return (
    <>
      <PageHeader
        title="Petty cash"
        actions={
          list.may.create && (
            <LinkButton href={`${PAGE}/new`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              New petty cash voucher
            </LinkButton>
          )
        }
      >
        Spending paid out of a petty cash fund, one voucher for each paper petty cash voucher, with the photo or PDF of every official receipt. It&apos;s entered and
        submitted, checked against its receipts by someone else, then posted to the books. Returned, it goes back with the reason.
      </PageHeader>
      {list.waitingForYou > 0 || list.waitingOnOthers > 0 ? (
        <p className="mb-3 text-sm text-ink-2">
          {list.waitingForYou > 0 && <span className="font-semibold text-ink">{list.waitingForYou === 1 ? "1 voucher is" : `${list.waitingForYou} vouchers are`} waiting for you.</span>}
          {list.waitingForYou > 0 && list.waitingOnOthers > 0 && " "}
          {list.waitingOnOthers > 0 && <>{list.waitingOnOthers === 1 ? "1 of yours is" : `${list.waitingOnOthers} of yours are`} waiting for someone else to check.</>}
        </p>
      ) : null}
      <ListFrame>
        {list.funds.length > 0 ? (
          <FigureStrip
            figures={list.funds.map((f) => ({
              // With its code: two funds can share a name (the chart has two "Petty Cash Fund - Finance"), and the
              // shared strip keys each figure by its label.
              label: `${f.code} ${f.name}${f.active ? "" : " (switched off)"} · in the books`,
              value: fmt.peso(f.balanceCentavos),
            }))}
          />
        ) : (
          <p className="border-b border-rule px-5 py-3 text-sm text-ink-2">
            No petty cash fund yet: vouchers are paid from an account under Cash named Petty Cash.{" "}
            <Link href="/finance/ledger/accounts" className="text-hema hover:underline">
              Chart of accounts
            </Link>
          </p>
        )}
        <UnderlineTabs label="Show" tabs={TABS.map((t) => ({ href: `${PAGE}?show=${t.key}`, label: t.label, count: list.counts[t.key], current: t.key === show }))} />
        <p className="border-b border-rule px-5 py-3 text-sm text-ink-2">
          {tab.says}
          {yours && " Your role can do this."}
        </p>
        <ListToolbar q={q} placeholder="Voucher number, person in charge or department" keep={{ show }}>
          {q && (
            <Link href={`${PAGE}?show=${show}`} className="text-meta text-hema hover:underline">
              Clear search
            </Link>
          )}
        </ListToolbar>
        {list.items.length === 0 ? (
          q ? (
            <Empty title="No vouchers match" icon="lists">
              Nothing here matches &ldquo;{q}&rdquo;. Try the voucher number or the person in charge.
            </Empty>
          ) : (
            <Empty title={tab.empty} icon="lists">
              {show === "draft" && list.may.create ? "Enter one with New petty cash voucher." : null}
            </Empty>
          )
        ) : (
          <ExpandableTable
            minWidth="56rem"
            columns={[
              { key: "number", label: "Voucher" },
              { key: "date", label: "Date" },
              { key: "fund", label: "Fund" },
              { key: "pic", label: "Person in charge" },
              { key: "receipts", label: "Receipts" },
              { key: "total", label: "Total", align: "right" },
              { key: "status", label: "Status" },
            ]}
            rows={list.items.map((x) => ({
              id: x.id,
              muted: x.status === "void",
              cells: [
                <Link key="n" href={`${PAGE}/${x.id}`} className="font-mono text-meta font-semibold text-hema hover:underline">
                  {x.number}
                </Link>,
                <span key="d" className="text-ink-2">
                  {fmt.dateLabel(x.voucherDate)}
                </span>,
                <span key="f">{x.fund.name}</span>,
                <span key="p">
                  {x.personInCharge ?? <span className="text-ink-3">—</span>}
                  {x.department && <span className="block text-meta text-ink-3">{x.department}</span>}
                </span>,
                <Receipts key="r" n={x.receipts} missing={x.missingReceipts} />,
                <span key="t">{fmt.peso(x.totalCentavos)}</span>,
                <StatusMark key="s" status={x.status} label={x.statusLabel} />,
              ],
              detail: (
                <p className="text-sm text-ink-2">
                  Entered by {x.createdBy} · paid out of {x.fund.code} · {x.fund.name}: <span className="font-semibold text-ink tabular-nums">{fmt.peso(x.paidOutCentavos)}</span> after tax
                  withheld ·{" "}
                  <Link href={`${PAGE}/${x.id}`} className="text-hema hover:underline">
                    Open the voucher
                  </Link>
                </p>
              ),
              actions: (
                <RowMenu
                  label={`Actions for ${x.number}`}
                  items={[
                    { label: "Open", icon: <ExternalLink />, href: `${PAGE}/${x.id}` },
                    { label: "Print with receipts", icon: <Printer />, href: `${PAGE}/${x.id}/print` },
                  ]}
                />
              ),
            }))}
          />
        )}
      </ListFrame>
      {list.limited && <p className="mt-2 px-1 text-meta text-ink-3">Showing the newest 200. Search to narrow the list.</p>}
    </>
  );
}

export async function NewPettyCashPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const crumbs = [{ href: PAGE, label: "Petty cash" }];
  if (!(me.permissions?.includes("petty_cash.create") ?? false)) {
    return (
      <>
        <PageHeader title="New petty cash voucher" crumbs={crumbs} />
        <Sheet>
          <Empty title="Your role can't add petty cash vouchers" icon="lists">
            Someone whose role may add petty cash vouchers enters them.
          </Empty>
        </Sheet>
      </>
    );
  }
  const choices = await load<PettyCashChoices>("/finance/petty-cash/choices");
  return (
    <>
      <PageHeader title="New petty cash voucher" crumbs={crumbs}>
        Saved as a draft first. Then attach the photo or PDF of each receipt on its line, and submit it for checking from the voucher&apos;s page.
      </PageHeader>
      <PettyCashEditor voucher={null} choices={choices} org={me.org} today={fmt.todayKey()} />
    </>
  );
}

export async function EditPettyCashPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const v = await load<PettyCashVoucher>(`/finance/petty-cash/${enc(id)}`);
  if (!v.canEdit) redirect(`${PAGE}/${v.id}`);
  const choices = await load<PettyCashChoices>("/finance/petty-cash/choices");
  return (
    <>
      <PageHeader title={`Edit ${v.number}`} crumbs={[{ href: PAGE, label: "Petty cash" }, { href: `${PAGE}/${v.id}`, label: v.number }]}>
        Change what was typed, add or remove receipt lines, and attach each receipt. A removed line takes its receipt with it.
      </PageHeader>
      <PettyCashEditor voucher={v} choices={choices} org={me.org} today={fmt.todayKey()} />
    </>
  );
}

/** Who acts next, said from the status (no names guessed: the role that acts). */
function nextStep(v: PettyCashVoucher, fmt: Format): string {
  if (v.status === "draft") return v.missingReceipts ? "A draft. Next: whoever made it attaches every receipt, then submits it for checking." : "A draft with every receipt attached. Next: whoever made it submits it for checking.";
  if (v.status === "returned") return "Returned for correction. Next: whoever made it corrects it and submits it again.";
  if (v.status === "to_check") return "Waiting to be checked by someone whose role may check petty cash, other than whoever made or submitted it.";
  if (v.status === "posted") return `Checked and posted${v.checkedBy ? ` by ${v.checkedBy}` : ""}${v.checkedAt ? `, ${fmt.whenLabel(v.checkedAt)}` : ""}. Nothing more to do; a mistake is voided with a reason.`;
  return `Voided${v.voidedBy ? ` by ${v.voidedBy}` : ""}${v.voidReason ? `: ${v.voidReason}` : ""}. Its entry was reversed on the day it was voided.`;
}

/** The voucher's receipts as print attachments: each read through its own permission-checked route. */
function receiptFiles(v: PettyCashVoucher): BillFile[] {
  return v.lines.flatMap((l) =>
    l.file ? [{ id: l.id, name: `Receipt ${l.position}: ${l.store}, ${l.receiptNumber} (${l.file.name})`, contentType: l.file.contentType, size: l.file.size, uploadedBy: l.file.uploadedBy, uploadedAt: l.file.uploadedAt ?? "" }] : [],
  );
}

function Totals({ v, fmt }: { v: PettyCashVoucher; fmt: Format }) {
  return (
    <div className="mt-4 ml-auto max-w-sm space-y-1 text-sm">
      <p className="flex justify-between gap-6">
        <span className="text-ink-2">Before VAT</span>
        <span className="tabular-nums">{fmt.peso(v.netCentavos)}</span>
      </p>
      <p className="flex justify-between gap-6">
        <span className="text-ink-2">VAT (input)</span>
        <span className="tabular-nums">{fmt.peso(v.vatCentavos)}</span>
      </p>
      <p className="flex justify-between gap-6 font-semibold">
        <span>Voucher total</span>
        <span className="tabular-nums">{fmt.peso(v.totalCentavos)}</span>
      </p>
      <p className="flex justify-between gap-6">
        <span className="text-ink-2">Tax withheld (EWT)</span>
        <span className="tabular-nums">({fmt.peso(v.withheldCentavos)})</span>
      </p>
      <p className="flex justify-between gap-6 border-t border-ink pt-1 font-semibold">
        <span>Paid out of the fund</span>
        <span className="tabular-nums">{fmt.peso(v.paidOutCentavos)}</span>
      </p>
    </div>
  );
}

const withheldLabel = (l: PettyCashVoucher["lines"][number]) => (l.withholding ? `${l.withholding} · ${(l.withholdingRateBp ?? 0) / 100}%` : "None");

export async function PettyCashVoucherPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const [v, signed] = await Promise.all([load<PettyCashVoucher>(`/finance/petty-cash/${enc(id)}`), load<{ steps: SignedStep[] }>(`/finance/signatures/petty_cash/${enc(id)}`)]);
  const when = fmt.on({ dateStyle: "medium", timeStyle: "short" });
  const lastReturn = [...v.events].reverse().find((e) => e.kind === "returned");
  const acts = v.canSubmit || v.canCheck || v.canReturn;
  const open = v.status === "draft" || v.status === "returned";

  return (
    <>
      <PrintAttachmentSources files={receiptFiles(v)} openBase={`${PAGE}/${v.id}/files`} />
      <PageHeader
        title={`Petty cash voucher ${v.number}`}
        crumbs={[{ href: PAGE, label: "Petty cash" }]}
        actions={
          <>
            {v.canEdit && <LinkButton href={`${PAGE}/${v.id}/edit`}>Edit</LinkButton>}
            {v.canDelete && <DeletePettyCash id={v.id} />}
            <LinkButton href={`${PAGE}/${v.id}/print`} icon={<Printer className="size-4" aria-hidden />}>
              Print with receipts
            </LinkButton>
            {v.canVoid && <VoidPettyCash id={v.id} number={v.number} />}
          </>
        }
      >
        <StatusMark status={v.status} label={v.statusLabel} />
        <span className="ml-2 text-meta text-ink-2">
          {fmt.peso(v.totalCentavos)} from {v.fund.name}
        </span>
      </PageHeader>

      {v.status === "returned" && lastReturn && (
        <p className="mb-4 rounded-[3px] bg-due-today/10 px-4 py-2 text-sm">
          <span className="font-semibold">Returned for correction</span> by {lastReturn.who}: {lastReturn.text}
        </p>
      )}

      <Sheet className="mb-5 px-5 py-4 print:hidden">
        <SectionTitle icon="approvals">Next step</SectionTitle>
        <p className={`text-sm ${acts ? "mb-3" : ""}`}>
          {nextStep(v, fmt)}
          {acts && <span className="font-semibold"> It&apos;s your turn.</span>}
        </p>
        {(acts || (open && v.canEdit)) && <PettyCashSteps voucher={v} />}
      </Sheet>

      <Sheet className="px-6 py-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <Particulars
            items={[
              ["Paper voucher", <span key="n" className="font-mono">{v.number}</span>],
              ["Paid from", `${v.fund.code} · ${v.fund.name}`],
              ["Voucher date", fmt.dateLabel(v.voucherDate)],
              ["Person in charge", v.personInCharge],
              ["Department", v.department],
            ]}
          />
          <Particulars
            items={[
              ["Entered by", v.createdBy],
              ["Submitted", v.submittedAt ? when.format(new Date(v.submittedAt)) : null],
              ["Checked and posted by", v.checkedBy ? `${v.checkedBy}${v.checkedAt ? `, ${when.format(new Date(v.checkedAt))}` : ""}` : null],
              ["Voided by", v.voidedBy ? `${v.voidedBy}${v.voidedAt ? `, ${when.format(new Date(v.voidedAt))}` : ""}: ${v.voidReason ?? ""}` : null],
            ]}
          />
        </div>
        {v.notes && <p className="mt-4 text-meta text-ink-2">{v.notes}</p>}
      </Sheet>

      <Sheet className="mt-5 px-5 py-4">
        <SectionTitle>Receipts</SectionTitle>
        <p className="mb-3 text-meta text-ink-2">
          Each receipt beside its line.{" "}
          {v.amountsIncludeVat ? "Amounts include VAT, as on the receipts." : "Amounts are before VAT."}
          {v.missingReceipts > 0 && <span className="font-semibold text-due-today"> {v.missingReceipts === 1 ? "1 receipt missing." : `${v.missingReceipts} receipts missing.`}</span>}
        </p>
        <ol className="space-y-4">
          {v.lines.map((l) => (
            <li key={l.id} className="grid gap-4 rounded-[3px] border border-rule p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <div className="min-w-0">
                <p className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold">
                    {l.position}. {l.store}
                  </span>
                  <span className="text-sm font-semibold tabular-nums">{fmt.peso(l.amountCentavos)}</span>
                </p>
                <Particulars
                  items={[
                    ["Receipt number", <span key="r" className="font-mono">{l.receiptNumber}</span>],
                    ["Receipt date", fmt.dateLabel(l.spentOn)],
                    ["Store TIN", l.storeTin],
                    ["Account", `${l.account.code} · ${l.account.name}`],
                    ["Description", l.description],
                    ["Purchase type", l.purchaseTypeLabel],
                    ["VAT", `${l.vatLabel} · ${fmt.peso(l.vatCentavos)}`],
                    ["Tax withheld", l.withholding ? `${withheldLabel(l)} · ${fmt.peso(l.withheldCentavos)}` : "None"],
                    ["Before VAT", fmt.peso(l.netCentavos)],
                  ]}
                />
              </div>
              <div className="min-w-0 space-y-2">
                {l.file ? <ReceiptPreview voucherId={v.id} lineId={l.id} file={l.file} /> : <p className="rounded-[3px] bg-due-today/10 px-3 py-4 text-sm text-due-today">Receipt missing: no photo or PDF attached yet.</p>}
                {v.canEdit && <ReceiptSlot voucherId={v.id} lineId={l.id} position={l.position} file={l.file} />}
              </div>
            </li>
          ))}
        </ol>
        <Totals v={v} fmt={fmt} />
      </Sheet>

      <Sheet className="mt-5 px-5 py-4">
        <SectionTitle>Signatures</SectionTitle>
        <SignatureLines
          lines={[
            { step: "prepared", label: "Prepared and submitted by" },
            { step: "checked", label: "Checked and posted by" },
          ]}
          signed={signed.steps}
          timeZone={me.org.timezone}
        />
      </Sheet>

      {v.events.length > 0 && (
        <Sheet className="mt-5 px-5 py-4">
          <SectionTitle>History</SectionTitle>
          <ul className="divide-y divide-rule text-sm">
            {v.events.map((e, i) => (
              <li key={i} className="grid gap-1 py-2 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4">
                <span className="text-ink-2 tabular-nums">{when.format(new Date(e.at))}</span>
                <span>
                  <span className="font-semibold">{e.who}</span> · {EVENT_LABELS[e.kind] ?? e.kind}
                  {e.text && <span className={e.kind === "returned" ? "text-due-today" : "text-ink-2"}>: {e.text}</span>}
                </span>
              </li>
            ))}
          </ul>
        </Sheet>
      )}

      <p className="mt-3 text-meta text-ink-3">
        Entered by {v.createdBy}, {when.format(new Date(v.createdAt))}.{" "}
        {v.entryId && (
          <Link href="/finance/ledger?source=petty_cash" className="text-hema hover:underline">
            View journal entries from petty cash
          </Link>
        )}
      </p>
    </>
  );
}

/** The voucher as it prints: its receipt lines, the totals, the e-signatures, then every receipt's pages. */
export async function PrintPettyCashPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const [v, signed] = await Promise.all([load<PettyCashVoucher>(`/finance/petty-cash/${enc(id)}`), load<{ steps: SignedStep[] }>(`/finance/signatures/petty_cash/${enc(id)}`)]);
  return (
    <>
      <PrintAttachmentSources files={receiptFiles(v)} openBase={`${PAGE}/${v.id}/files`} />
      <div className="print:hidden">
        <PageHeader crumbs={[{ href: PAGE, label: "Petty cash" }, { href: `${PAGE}/${v.id}`, label: v.number }]} title={`Petty cash voucher ${v.number}`} actions={<PrintButton />}>
          Print it, or choose &quot;Save as PDF&quot; in the print window. Every attached receipt prints after the voucher.
        </PageHeader>
        {v.missingReceipts > 0 && (
          <p className="mb-4 rounded-[3px] bg-due-today/10 px-4 py-2 text-sm">
            {v.missingReceipts === 1 ? "1 receipt isn't" : `${v.missingReceipts} receipts aren't`} attached yet, so {v.missingReceipts === 1 ? "it won't" : "they won't"} print.
          </p>
        )}
      </div>
      <Sheet className="relative px-8 py-7 print:border-0 print:shadow-none">
        {v.status !== "posted" && (
          <p className="mb-4 rounded-[3px] bg-danger-tint px-3 py-2 text-sm font-semibold text-danger">
            {v.status === "void" ? `Void${v.voidReason ? `: ${v.voidReason}` : ""}. Not in the books.` : `${v.statusLabel}: not posted yet.`}
          </p>
        )}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink pb-3">
          <div>
            <p className="finance-document-company-name text-meta text-ink-3 uppercase">{me.org.name}</p>
            <h2 className="text-heading">Petty cash voucher</h2>
          </div>
          <dl className="text-right text-sm">
            <div>
              <dt className="inline text-ink-3">No. </dt>
              <dd className="inline font-mono font-semibold">{v.number}</dd>
            </div>
            <div>
              <dt className="inline text-ink-3">Date </dt>
              <dd className="inline">{fmt.dateLabel(v.voucherDate)}</dd>
            </div>
          </dl>
        </div>
        <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2 print:grid-cols-2">
          <div>
            <dt className="inline text-ink-3">Paid from: </dt>
            <dd className="inline font-semibold">
              {v.fund.code} · {v.fund.name}
            </dd>
          </div>
          {v.personInCharge && (
            <div>
              <dt className="inline text-ink-3">Person in charge: </dt>
              <dd className="inline">{v.personInCharge}</dd>
            </div>
          )}
          {v.department && (
            <div>
              <dt className="inline text-ink-3">Department: </dt>
              <dd className="inline">{v.department}</dd>
            </div>
          )}
        </dl>
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="py-2 font-semibold">#</th>
              <th className="py-2 font-semibold">Date</th>
              <th className="py-2 font-semibold">Store · TIN</th>
              <th className="py-2 font-semibold">Receipt no.</th>
              <th className="py-2 font-semibold">Account · description</th>
              <th className="py-2 font-semibold">VAT · withheld</th>
              <th className="py-2 text-right font-semibold">Amount</th>
            </tr>
          </thead>
          <tbody>
            {v.lines.map((l) => (
              <tr key={l.id} className="border-b border-rule align-top">
                <td className="py-1.5">{l.position}</td>
                <td className="py-1.5">{fmt.dateLabel(l.spentOn)}</td>
                <td className="py-1.5">
                  {l.store}
                  {l.storeTin && <span className="block text-meta text-ink-3">TIN {l.storeTin}</span>}
                </td>
                <td className="py-1.5 font-mono">{l.receiptNumber}</td>
                <td className="py-1.5">
                  {l.account.code} · {l.account.name}
                  {l.description && <span className="block text-meta text-ink-3">{l.description}</span>}
                  <span className="block text-meta text-ink-3">{l.purchaseTypeLabel}</span>
                </td>
                <td className="py-1.5 text-meta">
                  {l.vatLabel}
                  <span className="block text-ink-3">{withheldLabel(l)}</span>
                </td>
                <td className="py-1.5 text-right tabular-nums">{fmt.peso(l.amountCentavos)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Totals v={v} fmt={fmt} />
        {v.notes && <p className="mt-3 text-meta text-ink-2">{v.notes}</p>}
        <SignatureLines
          lines={[
            { step: "prepared", label: "Prepared and submitted by" },
            { step: "checked", label: "Checked and posted by" },
          ]}
          signed={signed.steps}
          timeZone={me.org.timezone}
        />
      </Sheet>
    </>
  );
}
