"use client";

import { RotateCcw, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import type { ModuleKey } from "@/src/platform/lib/modules";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Dots } from "@/src/platform/ui/dots";
import { SearchInput } from "@/src/platform/ui/field";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { cleanupRecords, deleteRecords, eraseFromBin, restoreFromBin, type BinItem, type CleanupKind, type CleanupRecord } from "./actions";

// Data clean-up (2026-10-30), the same in every app: pick a kind of record, find and tick the ones to go,
// delete them to the recycle bin; restore or erase them there. Posted documents ask twice.

const day = (iso: string) => new Date(iso).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric", timeZone: "Asia/Manila" });
const left = (iso: string) => Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000));

export function CleanupBoard({ module, path, kinds, bin, days }: { module: ModuleKey; path: string; kinds: CleanupKind[]; bin: BinItem[]; days: number }) {
  const router = useRouter();
  const [tab, setTab] = useState<"clean" | "bin">("clean");
  const [kind, setKind] = useState<CleanupKind | null>(null);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<{ items: CleanupRecord[]; total: number; pageSize: number } | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [loading, start] = useTransition();

  useEffect(() => {
    if (!kind) return;
    start(async () => {
      const r = await cleanupRecords(module, kind.key, q, page);
      if (!r.ok) return void toast.error(r.error);
      setRows(r.data);
    });
  }, [module, kind, q, page]);

  function pick(k: CleanupKind) {
    setKind(k);
    setQ("");
    setPage(1);
    setPicked(new Set());
    setRows(null);
  }

  const groups = [...new Set(kinds.map((k) => k.group))];
  const shownIds = rows?.items.map((r) => r.id) ?? [];
  const allPicked = shownIds.length > 0 && shownIds.every((id) => picked.has(id));
  const postedPicked = rows?.items.some((r) => r.posted && picked.has(r.id)) ?? false;

  async function remove(confirmPosted: boolean) {
    if (!kind) return false;
    const r = await deleteRecords(module, kind.key, [...picked], confirmPosted, path);
    if (!r.ok) {
      toast.error(r.error);
      return false;
    }
    toast.success(`${r.data.deleted} moved to the recycle bin`, { description: `Restorable for ${days} days.` });
    setPicked(new Set());
    setRows(null);
    setPage(1);
    const again = await cleanupRecords(module, kind.key, q, 1);
    if (again.ok) setRows(again.data);
    router.refresh();
  }

  return (
    <div className="space-y-4">
      <div className="inline-flex rounded-lg border border-rule bg-sheet p-1" role="tablist">
        {(["clean", "bin"] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-1.5 text-sm ${tab === t ? "bg-hema text-white" : "text-ink-2 hover:bg-bench"}`}
          >
            {t === "clean" ? "Clean up" : `Recycle bin${bin.length ? ` (${bin.length})` : ""}`}
          </button>
        ))}
      </div>

      {tab === "clean" ? (
        <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <Sheet className="px-3 py-3">
            {groups.map((g) => (
              <div key={g} className="mb-3 last:mb-0">
                <p className="px-2 pb-1 text-meta font-semibold text-ink-3">{g === "Set-up" ? "Set-up lists" : g}</p>
                <ul>
                  {kinds
                    .filter((k) => k.group === g)
                    .map((k) => (
                      <li key={k.key}>
                        <button
                          type="button"
                          onClick={() => pick(k)}
                          className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm ${kind?.key === k.key ? "bg-hema-tint font-semibold text-ink" : "text-ink-2 hover:bg-bench"}`}
                        >
                          <span className="truncate">{k.name}</span>
                          <span className="ml-2 shrink-0 text-meta text-ink-3">{k.count}</span>
                        </button>
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </Sheet>
          <Sheet className="px-5 py-4">
            {!kind ? (
              <Empty icon="lists" title="Pick what to clean up">
                Choose a kind of record on the left, then tick the ones to delete. They go to the recycle bin for {days} days, and can be restored.
              </Empty>
            ) : (
              <>
                <SectionTitle icon="lists">{kind.name}</SectionTitle>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <div className="w-full max-w-xs">
                    <SearchInput placeholder={`Find in ${kind.name.toLowerCase()}`} allowClear onSearch={(v) => (setQ(v), setPage(1))} />
                  </div>
                  <span className="text-meta text-ink-3">{rows ? `${rows.total} in all` : ""}</span>
                  <span className="ml-auto">
                    {postedPicked ? (
                      <ConfirmButton
                        label={`Delete ${picked.size}`}
                        icon={<Trash2 className="size-4" aria-hidden />}
                        triggerVariant="danger"
                        disabled={picked.size === 0}
                        title={`Delete ${picked.size} including posted documents?`}
                        body="Posted documents change the books or the stock: deleting one takes its journal entries or stock movements with it. BIR expects issued invoices to be voided rather than deleted. They stay restorable in the recycle bin."
                        confirmLabel="Delete them anyway"
                        onConfirm={() => remove(true)}
                      />
                    ) : (
                      <ConfirmButton
                        label={`Delete ${picked.size || ""}`.trim()}
                        icon={<Trash2 className="size-4" aria-hidden />}
                        triggerVariant="danger"
                        disabled={picked.size === 0}
                        title={`Delete ${picked.size} ${picked.size === 1 ? "record" : "records"}?`}
                        body={`They go to the recycle bin, with what belongs only to them, and can be restored for ${days} days.`}
                        confirmLabel="Delete"
                        onConfirm={() => remove(false)}
                      />
                    )}
                  </span>
                </div>
                {!rows || loading ? (
                  <div className="grid place-items-center py-12">
                    <Dots label={`Loading ${kind.name.toLowerCase()}`} />
                  </div>
                ) : rows.items.length === 0 ? (
                  <Empty icon="lists" title="Nothing here">
                    {q ? "Nothing matches that search." : `No ${kind.name.toLowerCase()} left.`}
                  </Empty>
                ) : (
                  <>
                    <ul className="mt-3 divide-y divide-rule">
                      <li className="flex items-center gap-3 py-2 text-meta text-ink-3">
                        <input
                          type="checkbox"
                          aria-label="Tick every one shown"
                          checked={allPicked}
                          onChange={(e) => setPicked(new Set(e.target.checked ? [...picked, ...shownIds] : [...picked].filter((id) => !shownIds.includes(id))))}
                        />
                        Every one shown
                      </li>
                      {rows.items.map((r) => (
                        <li key={r.id} className="flex items-center gap-3 py-2 text-sm">
                          <input
                            type="checkbox"
                            aria-label={`Tick ${r.label}`}
                            checked={picked.has(r.id)}
                            onChange={(e) => {
                              const next = new Set(picked);
                              if (e.target.checked) next.add(r.id);
                              else next.delete(r.id);
                              setPicked(next);
                            }}
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-ink">{r.label}</span>
                            {r.sub && <span className="block truncate text-meta text-ink-3">{r.sub}</span>}
                          </span>
                          {r.posted && <span className="rounded-full bg-promo-tint px-2 py-0.5 text-meta text-promo-ink">Posted</span>}
                          {r.createdAt && <span className="shrink-0 text-meta text-ink-3">{day(r.createdAt)}</span>}
                        </li>
                      ))}
                    </ul>
                    {rows.total > rows.pageSize && (
                      <div className="mt-3 flex items-center justify-end gap-2 text-meta text-ink-3">
                        <Button size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>
                          Previous
                        </Button>
                        Page {page} of {Math.ceil(rows.total / rows.pageSize)}
                        <Button size="sm" disabled={page * rows.pageSize >= rows.total} onClick={() => setPage(page + 1)}>
                          Next
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </Sheet>
        </div>
      ) : (
        <Sheet className="px-5 py-4">
          <SectionTitle
            icon="lists"
            action={
              bin.length > 0 ? (
                <ConfirmButton
                  label="Empty the recycle bin"
                  triggerSize="sm"
                  triggerVariant="danger"
                  title={`Erase all ${bin.length} for good?`}
                  body="They can't be restored afterwards."
                  confirmLabel="Erase all"
                  onConfirm={async () => {
                    const r = await eraseFromBin(module, null, path);
                    if (!r.ok) return void toast.error(r.error), false;
                    toast.success(`${r.data.erased} erased`);
                    router.refresh();
                  }}
                />
              ) : undefined
            }
          >
            Recycle bin
          </SectionTitle>
          <p className="mt-1 text-meta text-ink-3">Deleted records stay here {days} days, then are erased. Restore puts a record back with everything that went with it.</p>
          {bin.length === 0 ? (
            <Empty icon="lists" title="The recycle bin is empty">
              What you delete under Clean up comes here.
            </Empty>
          ) : (
            <ul className="mt-3 divide-y divide-rule">
              {bin.map((b) => (
                <li key={b.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-ink">{b.label}</span>
                    <span className="block text-meta text-ink-3">
                      {b.kindName}
                      {b.rows > 1 ? ` · with ${b.rows - 1} ${b.rows - 1 === 1 ? "row" : "rows"} of its own` : ""} · deleted {day(b.deletedAt)} by {b.deletedBy} · erased in {left(b.expiresAt)}{" "}
                      {left(b.expiresAt) === 1 ? "day" : "days"}
                    </span>
                  </span>
                  <AsyncButton
                    size="sm"
                    icon={<RotateCcw className="size-4" aria-hidden />}
                    onRun={async () => {
                      const r = await restoreFromBin(module, b.id, path);
                      if (!r.ok) return void toast.error(r.error);
                      toast.success(`${b.label} is back`);
                      router.refresh();
                    }}
                  >
                    Restore
                  </AsyncButton>
                  <ConfirmButton
                    label="Erase"
                    triggerSize="sm"
                    title={`Erase ${b.label} for good?`}
                    body="It can't be restored afterwards."
                    confirmLabel="Erase"
                    onConfirm={async () => {
                      const r = await eraseFromBin(module, b.id, path);
                      if (!r.ok) return void toast.error(r.error), false;
                      router.refresh();
                    }}
                  />
                </li>
              ))}
            </ul>
          )}
        </Sheet>
      )}
    </div>
  );
}
