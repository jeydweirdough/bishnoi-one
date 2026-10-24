import { ArrowRightLeft, Building, CircleCheck, ClipboardList, FilePenLine, Hourglass, Lock, PackageCheck, PackageOpen, ScanBarcode, Send, Truck, User, Warehouse } from "lucide-react";
import { Board, type BoardCard, type BoardColumn, type BoardMove } from "@/src/modules/inventory/platform/ui/board";
import { orderStep, purchaseOrderStep, transferStep } from "@/src/modules/inventory/actions/inventory";
import { kindOf } from "@/src/modules/inventory/lib/order-kinds";
import type { OrderBrief, POBrief, TransferBrief } from "@/src/modules/inventory/lib/types";

// Each document's board: its columns, how a card reads (as the CRM's deal cards
// do), and the moves each step allows, gated by the same permissions as the
// step's button on its page.

type Fmt = { count: (n: number) => string; peso: (n: number) => string };
type Day = (key: string | null) => string;
type May = (permission: string) => boolean;
type Run = (id: string, step: string) => Promise<{ ok: true; data?: unknown } | { ok: false; error: string }>;

// Finished work stays in view for a while; the rest is one link away.
const KEEP_DONE = 12;

const DOT = { waiting: "#b5b5b0", under: "#d48806", moving: "#2f54eb", done: "#4f7f44" };

const thisYear = String(new Date().getFullYear());
/** This year's dates without the year: "Oct 1". */
const short = (label: string) => label.replace(new RegExp(`,? ${thisYear}$`), "");

const lines = (n: number) => `${n} line${n === 1 ? "" : "s"}`;

/** Only the moves this person may make. */
const allowed = (moves: (BoardMove & { may: boolean })[]): BoardMove[] => moves.filter((m) => m.may).map(({ may: _, ...m }) => m);

/** The latest few finished, with how many more there are. */
function recentDone<T extends { id: string }>(all: T[], done: (x: T) => boolean) {
  const finished = all.filter(done);
  return { keep: new Set(finished.slice(0, KEEP_DONE).map((x) => x.id)), hidden: Math.max(0, finished.length - KEEP_DONE) };
}

/** A small word beside a card's title: what kind of order it is. */
function Tag({ children }: { children: string }) {
  return <span className="rounded-md bg-bench px-2 py-0.5 text-[0.6875rem] text-ink-2">{children}</span>;
}

export function OrdersBoard({ orders, fmt, day, may, kind }: { orders: OrderBrief[]; fmt: Fmt; day: Day; may: May; kind?: string }) {
  const today = new Date().toISOString().slice(0, 10);
  const { keep, hidden } = recentDone(orders, (o) => o.status === "issued");
  const shown = orders.filter((o) => o.status !== "cancelled" && (o.status !== "issued" || keep.has(o.id)));
  const units = (status: string) => shown.filter((o) => o.status === status).reduce((n, o) => n + o.units, 0);
  const columns: BoardColumn[] = [
    { key: "draft", label: "Draft", dot: DOT.waiting, icon: <FilePenLine />, note: `${fmt.count(units("draft"))} units`, hint: "Created; no stock reserved" },
    { key: "confirmed", label: "Reserved", dot: DOT.under, icon: <Lock />, note: `${fmt.count(units("confirmed"))} units held`, hint: "Confirmed; stock reserved" },
    { key: "picking", label: "Picking", dot: DOT.moving, icon: <ScanBarcode />, note: `${fmt.count(units("picking"))} units`, hint: "Being picked" },
    { key: "issued", label: "Issued", dot: DOT.done, icon: <CircleCheck />, note: "Recent", hint: "Stock issued" },
  ];
  const cards: BoardCard[] = shown.map((o) => {
    const open = o.status !== "issued";
    const late = open && o.neededOn !== null && o.neededOn < today;
    const info = kindOf(o.kind);
    return {
      id: o.id,
      column: o.status,
      href: `/inventory/orders/${o.id}`,
      title: o.number,
      flag: kind ? undefined : <Tag>{info?.plural.replace(/ orders$| requests$/, "") ?? o.kind}</Tag>,
      sub: o.recipient,
      subIcon: <User />,
      value: info?.priced && o.total ? fmt.peso(o.total) : `${fmt.count(o.units)} units`,
      when: open ? (o.neededOn ? (o.neededOn === today ? "Required today" : `Required ${short(day(o.neededOn))}`) : undefined) : o.issuedAt ? `Issued ${short(day(o.issuedAt.slice(0, 10)))}` : undefined,
      late,
      meta: `${lines(o.lineCount)} · from ${o.warehouse.code}`,
      metaIcon: <Warehouse />,
    };
  });
  const moves = allowed([
    { from: "draft", to: "confirmed", step: "confirm", label: "Confirm and reserve stock", may: may("orders.approve") },
    { from: "confirmed", to: "picking", step: "pick", label: "Start picking", may: may("orders.issue") || may("orders.approve") },
    { from: "confirmed", to: "issued", open: "/inventory/orders/{id}#issue", label: "Issue", may: may("orders.issue") },
    { from: "picking", to: "issued", open: "/inventory/orders/{id}#issue", label: "Issue", may: may("orders.issue") },
  ]);
  const k = kind ? `&kind=${kind}` : "";
  return (
    <Board
      columns={columns}
      cards={cards}
      moves={moves}
      run={orderStep as Run}
      newHref={may("orders.create") ? (kindOf(kind) ? `/inventory/orders/new/${kindOf(kind)!.slug}` : "/inventory/orders/new") : undefined}
      more={{ issued: { href: `/inventory/orders?view=list&status=issued${k}`, label: hidden ? `All issued (${fmt.count(hidden + KEEP_DONE)})` : "Issued (list view)" } }}
    />
  );
}

export function PurchaseOrdersBoard({ orders, fmt, day, may }: { orders: POBrief[]; fmt: Fmt; day: Day; may: May }) {
  const { keep, hidden } = recentDone(orders, (o) => o.status === "received");
  const shown = orders.filter((o) => o.status !== "cancelled" && (o.status !== "received" || keep.has(o.id)));
  const worth = (status: string) => fmt.peso(shown.filter((o) => o.status === status).reduce((n, o) => n + o.total, 0));
  const columns: BoardColumn[] = [
    { key: "draft", label: "Draft", dot: DOT.waiting, icon: <FilePenLine />, note: worth("draft"), hint: "Not yet placed with the supplier" },
    { key: "ordered", label: "Ordered", dot: DOT.under, icon: <Send />, note: worth("ordered"), hint: "Placed; awaiting delivery" },
    { key: "partial", label: "Partially received", dot: DOT.moving, icon: <PackageOpen />, note: worth("partial"), hint: "Balance outstanding" },
    { key: "received", label: "Received", dot: DOT.done, icon: <PackageCheck />, note: "Recent", hint: "Fully received" },
  ];
  const cards: BoardCard[] = shown.map((o) => ({
    id: o.id,
    column: o.status,
    href: `/inventory/purchase-orders/${o.id}`,
    title: o.number,
    sub: o.supplier.name,
    subIcon: <Building />,
    value: fmt.peso(o.total),
    when: o.status !== "received" && o.expectedOn ? `Due ${short(day(o.expectedOn))}` : undefined,
    late: o.late,
    meta: o.status === "partial" ? `${fmt.count(o.received)} of ${fmt.count(o.ordered)} received · to ${o.warehouse.code}` : `${lines(o.lineCount)} · to ${o.warehouse.code}`,
    metaIcon: <Warehouse />,
  }));
  const receive = may("receiving.receive");
  const moves = allowed([
    { from: "draft", to: "ordered", step: "place", label: "Place order", confirm: "Place this order with the supplier? Once placed, it cannot be edited, only received or cancelled.", may: may("purchasing.approve") },
    { from: "ordered", to: "partial", open: "/inventory/purchase-orders/{id}#receive", label: "Receive", may: receive },
    { from: "ordered", to: "received", open: "/inventory/purchase-orders/{id}#receive", label: "Receive", may: receive },
    { from: "partial", to: "received", open: "/inventory/purchase-orders/{id}#receive", label: "Receive remaining", may: receive },
  ]);
  return (
    <Board
      columns={columns}
      cards={cards}
      moves={moves}
      run={purchaseOrderStep as Run}
      newHref={may("purchasing.create") ? "/inventory/purchase-orders/new" : undefined}
      more={{ received: { href: "/inventory/purchase-orders?view=list&status=received", label: hidden ? `All received (${fmt.count(hidden + KEEP_DONE)})` : "Received (list view)" } }}
    />
  );
}

export function TransfersBoard({ transfers, fmt, day, may }: { transfers: TransferBrief[]; fmt: Fmt; day: Day; may: May }) {
  const { keep, hidden } = recentDone(transfers, (t) => t.status === "received");
  const shown = transfers.filter((t) => t.status !== "cancelled" && (t.status !== "received" || keep.has(t.id)));
  const units = (status: string) => `${fmt.count(shown.filter((t) => t.status === status).reduce((n, t) => n + t.units, 0))} units`;
  const columns: BoardColumn[] = [
    { key: "draft", label: "Draft", dot: DOT.waiting, icon: <FilePenLine />, note: units("draft"), hint: "Not yet requested" },
    { key: "requested", label: "Requested", dot: DOT.waiting, icon: <Hourglass />, note: units("requested"), hint: "Pending approval" },
    { key: "approved", label: "Approved", dot: DOT.under, icon: <ClipboardList />, note: units("approved"), hint: "Ready to dispatch" },
    { key: "in_transit", label: "In transit", dot: DOT.moving, icon: <Truck />, note: units("in_transit"), hint: "Dispatched" },
    { key: "received", label: "Received", dot: DOT.done, icon: <PackageCheck />, note: "Recent", hint: "Received at destination" },
  ];
  const dateOf = (iso: string | null) => short(day(iso ? iso.slice(0, 10) : null));
  const cards: BoardCard[] = shown.map((t) => ({
    id: t.id,
    column: t.status,
    href: `/inventory/transfers/${t.id}`,
    title: t.number,
    sub: `${t.from.name} → ${t.to.name}`,
    subIcon: <ArrowRightLeft />,
    value: `${fmt.count(t.units)} units`,
    when: t.status === "received" ? `Received ${dateOf(t.receivedAt)}` : t.status === "in_transit" ? `Dispatched ${dateOf(t.dispatchedAt)}` : t.requestedAt ? `Requested ${dateOf(t.requestedAt)}` : undefined,
    meta: lines(t.lineCount),
  }));
  const moves = allowed([
    { from: "draft", to: "requested", step: "request", label: "Submit request", may: may("transfers.create") },
    { from: "requested", to: "approved", step: "approve", label: "Approve", may: may("transfers.approve") },
    { from: "approved", to: "in_transit", open: "/inventory/transfers/{id}#dispatch", label: "Dispatch", may: may("transfers.dispatch") },
    { from: "in_transit", to: "received", open: "/inventory/transfers/{id}#receive", label: "Receive", may: may("transfers.receive") },
  ]);
  return (
    <Board
      columns={columns}
      cards={cards}
      moves={moves}
      run={transferStep as Run}
      newHref={may("transfers.create") ? "/inventory/transfers/new" : undefined}
      more={{ received: { href: "/inventory/transfers?view=list&status=received", label: hidden ? `All received (${fmt.count(hidden + KEEP_DONE)})` : "Received (list view)" } }}
    />
  );
}
