"use client";

import { Modal, Tabs } from "antd";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BarChart3,
  Columns,
  Filter,
  Layers,
  Plus,
  Save,
  Share2,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Input } from "@/src/platform/ui/field";
import {
  applyDefinition,
  type Definition,
  type FilterOp,
  type Measure,
  MEASURES,
  OPS,
  type SavedReport,
  isNumeric,
} from "./custom";
import { changeReport, saveReport } from "./custom-actions";
import type { ReportColumn, ReportData } from "./types";

interface Props {
  open: boolean;
  onClose: () => void;
  base: ReportData;
  app: string;
  initial?: SavedReport | null;
  baseAddress: string;
  onSaved?: (saved: SavedReport) => void;
}

export function ReportBuilderModal({
  open,
  onClose,
  base,
  app,
  initial,
  baseAddress,
  onSaved,
}: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // State
  const [name, setName] = useState(
    initial?.name ?? `${base.title} (Custom)`,
  );
  const [shared, setShared] = useState(initial?.shared ?? false);
  const [selectedCols, setSelectedCols] = useState<string[]>(
    initial?.definition.columns && initial.definition.columns.length > 0
      ? initial.definition.columns
      : base.columns.map((c) => c.key),
  );
  const [filters, setFilters] = useState<
    { column: string; op: FilterOp; value: string }[]
  >(
    (initial?.definition.filters ?? []).map((f) => ({
      column: f.column,
      op: f.op,
      value: f.value ?? "",
    })),
  );
  const [groupBy, setGroupBy] = useState<string>(
    initial?.definition.groupBy ?? "",
  );
  const [measures, setMeasures] = useState<Record<string, Measure>>(
    initial?.definition.measures ?? {},
  );
  const [sortCol, setSortCol] = useState<string>(
    initial?.definition.sort?.[0]?.column ?? "",
  );
  const [sortDesc, setSortDesc] = useState<boolean>(
    initial?.definition.sort?.[0]?.desc ?? false,
  );
  const [chart, setChart] = useState<"none" | "bar" | "line">(
    initial?.definition.chart ?? "none",
  );
  const [activeTab, setActiveTab] = useState("columns");

  // Reordering helpers for columns
  const moveColumn = (index: number, direction: "up" | "down") => {
    const next = [...selectedCols];
    const target = direction === "up" ? index - 1 : index + 1;
    if (target < 0 || target >= next.length) return;
    const temp = next[index];
    next[index] = next[target];
    next[target] = temp;
    setSelectedCols(next);
  };

  const toggleColumn = (key: string) => {
    if (selectedCols.includes(key)) {
      if (selectedCols.length <= 1) {
        toast.error("A report must have at least one column.");
        return;
      }
      setSelectedCols(selectedCols.filter((k) => k !== key));
    } else {
      setSelectedCols([...selectedCols, key]);
    }
  };

  // Filter helpers
  const addFilter = () => {
    const firstCol = base.columns[0]?.key ?? "";
    setFilters([...filters, { column: firstCol, op: "is", value: "" }]);
  };

  const removeFilter = (index: number) => {
    setFilters(filters.filter((_, i) => i !== index));
  };

  const updateFilter = (
    index: number,
    field: "column" | "op" | "value",
    val: string,
  ) => {
    setFilters(
      filters.map((f, i) => (i === index ? { ...f, [field]: val } : f)),
    );
  };

  // Preview computation
  const currentDef = useMemo<Definition>(
    () => ({
      columns: selectedCols,
      filters: filters
        .filter((f) => f.column)
        .map((f) => ({ column: f.column, op: f.op, value: f.value })),
      groupBy: groupBy || null,
      measures,
      sort: sortCol ? [{ column: sortCol, desc: sortDesc }] : [],
      chart,
    }),
    [selectedCols, filters, groupBy, measures, sortCol, sortDesc, chart],
  );

  const preview = useMemo(() => {
    try {
      return applyDefinition(base, currentDef, name);
    } catch {
      return base;
    }
  }, [base, currentDef, name]);

  const handleSave = () => {
    if (!name.trim()) {
      toast.error("Please enter a name for the report.");
      return;
    }

    startTransition(async () => {
      if (initial) {
        const res = await changeReport(initial.id, {
          name: name.trim(),
          definition: currentDef,
          shared,
        });
        if (!res.ok) {
          toast.error(res.error);
          return;
        }
        toast.success("Report updated successfully");
        onSaved?.(res.data);
        onClose();
        router.refresh();
      } else {
        const res = await saveReport({
          app,
          baseKey: base.key,
          name: name.trim(),
          definition: currentDef,
          shared,
        });
        if (!res.ok) {
          toast.error(res.error);
          return;
        }
        toast.success("Custom report saved");
        onSaved?.(res.data);
        onClose();
        router.push(`${baseAddress}?saved=${encodeURIComponent(res.data.id)}`);
      }
    });
  };

  const numericCols = useMemo(
    () => base.columns.filter((c) => isNumeric(c)),
    [base.columns],
  );

  const tabItems = [
    {
      key: "columns",
      label: (
        <span className="flex items-center gap-1.5">
          <Columns className="size-4" /> Columns ({selectedCols.length})
        </span>
      ),
      children: (
        <div className="space-y-4 py-2">
          <p className="text-sm text-ink-3">
            Choose which columns to include and order them as you want them
            displayed.
          </p>
          <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
            {selectedCols.map((colKey, index) => {
              const col = base.columns.find((c) => c.key === colKey);
              if (!col) return null;
              return (
                <div
                  key={colKey}
                  className="flex items-center justify-between rounded-lg border border-rule bg-bench/50 px-3 py-2 text-sm"
                >
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={true}
                      onChange={() => toggleColumn(colKey)}
                      className="size-4 rounded border-rule text-ink"
                    />
                    <span className="font-medium text-ink">{col.label}</span>
                    <span className="rounded bg-mint-2 px-1.5 py-0.5 text-meta text-sage-deep uppercase font-semibold">
                      {col.kind}
                    </span>
                  </label>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={index === 0}
                      onClick={() => moveColumn(index, "up")}
                      className="grid size-7 place-items-center rounded text-ink-3 hover:bg-white hover:text-ink disabled:opacity-30"
                      title="Move up"
                    >
                      <ArrowUp className="size-4" />
                    </button>
                    <button
                      type="button"
                      disabled={index === selectedCols.length - 1}
                      onClick={() => moveColumn(index, "down")}
                      className="grid size-7 place-items-center rounded text-ink-3 hover:bg-white hover:text-ink disabled:opacity-30"
                      title="Move down"
                    >
                      <ArrowDown className="size-4" />
                    </button>
                  </div>
                </div>
              );
            })}

            {/* Unselected columns */}
            {base.columns
              .filter((c) => !selectedCols.includes(c.key))
              .map((col) => (
                <div
                  key={col.key}
                  className="flex items-center justify-between rounded-lg border border-rule/50 bg-white/50 px-3 py-2 text-sm opacity-60"
                >
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={false}
                      onChange={() => toggleColumn(col.key)}
                      className="size-4 rounded border-rule text-ink"
                    />
                    <span className="text-ink-2">{col.label}</span>
                    <span className="rounded bg-bench px-1.5 py-0.5 text-meta text-ink-3 uppercase">
                      {col.kind}
                    </span>
                  </label>
                </div>
              ))}
          </div>
        </div>
      ),
    },
    {
      key: "filters",
      label: (
        <span className="flex items-center gap-1.5">
          <Filter className="size-4" /> Filters ({filters.length})
        </span>
      ),
      children: (
        <div className="space-y-4 py-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-ink-3">
              Only rows that match all conditions will be included in the report.
            </p>
            <Button size="sm" variant="default" onClick={addFilter}>
              <Plus className="mr-1 size-3.5" /> Add filter
            </Button>
          </div>

          {filters.length === 0 ? (
            <div className="rounded-xl border border-dashed border-rule py-8 text-center text-sm text-ink-3">
              No filters applied. All rows from the base report are included.
            </div>
          ) : (
            <div className="space-y-3">
              {filters.map((f, idx) => {
                const targetCol = base.columns.find((c) => c.key === f.column);
                const allowedOps = OPS.filter(
                  (op) =>
                    !op.kinds || (targetCol && op.kinds.includes(targetCol.kind)),
                );
                const needsVal =
                  OPS.find((o) => o.value === f.op)?.needs ?? true;

                return (
                  <div
                    key={idx}
                    className="flex flex-wrap items-center gap-2 rounded-xl border border-rule bg-bench/30 p-2.5"
                  >
                    <select
                      value={f.column}
                      onChange={(e) =>
                        updateFilter(idx, "column", e.target.value)
                      }
                      className="h-9 rounded-lg border border-rule bg-white px-2 text-sm font-medium text-ink"
                    >
                      {base.columns.map((c) => (
                        <option key={c.key} value={c.key}>
                          {c.label}
                        </option>
                      ))}
                    </select>

                    <select
                      value={f.op}
                      onChange={(e) =>
                        updateFilter(idx, "op", e.target.value as FilterOp)
                      }
                      className="h-9 rounded-lg border border-rule bg-white px-2 text-sm text-ink"
                    >
                      {allowedOps.map((op) => (
                        <option key={op.value} value={op.value}>
                          {op.label}
                        </option>
                      ))}
                    </select>

                    {needsVal && (
                      <input
                        type={
                          targetCol?.kind === "date"
                            ? "date"
                            : targetCol?.kind === "number" ||
                                targetCol?.kind === "money"
                              ? "number"
                              : "text"
                        }
                        value={f.value}
                        onChange={(e) =>
                          updateFilter(idx, "value", e.target.value)
                        }
                        placeholder="Value..."
                        className="h-9 min-w-32 flex-1 rounded-lg border border-rule bg-white px-2.5 text-sm"
                      />
                    )}

                    <button
                      type="button"
                      onClick={() => removeFilter(idx)}
                      className="grid size-8 place-items-center rounded text-ink-3 hover:bg-danger/10 hover:text-danger"
                      title="Remove filter"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "group",
      label: (
        <span className="flex items-center gap-1.5">
          <Layers className="size-4" /> Grouping & Totals
        </span>
      ),
      children: (
        <div className="space-y-4 py-2">
          <p className="text-sm text-ink-3">
            Summarise results by grouping rows with the same value together.
          </p>

          <div>
            <label className="block mb-1.5 text-sm font-medium text-ink">
              Group by
            </label>
            <select
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value)}
              className="h-9 w-full rounded-lg border border-rule bg-white px-3 text-sm text-ink"
            >
              <option value="">(None - show individual rows)</option>
              {base.columns
                .filter((c) => !isNumeric(c))
                .map((c) => (
                  <option key={c.key} value={c.key}>
                    {c.label}
                  </option>
                ))}
            </select>
          </div>

          {groupBy && numericCols.length > 0 && (
            <div className="rounded-xl border border-rule bg-bench/30 p-4 space-y-3">
              <h4 className="text-sm font-semibold text-ink">
                Calculate for numeric columns
              </h4>
              <div className="space-y-2">
                {numericCols.map((c) => (
                  <div
                    key={c.key}
                    className="flex items-center justify-between gap-4"
                  >
                    <span className="text-sm text-ink-2">{c.label}</span>
                    <select
                      value={measures[c.key] ?? "sum"}
                      onChange={(e) =>
                        setMeasures({
                          ...measures,
                          [c.key]: e.target.value as Measure,
                        })
                      }
                      className="h-8 rounded-md border border-rule bg-white px-2 text-xs"
                    >
                      {MEASURES.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ),
    },
    {
      key: "sort",
      label: (
        <span className="flex items-center gap-1.5">
          <ArrowUpDown className="size-4" /> Sorting
        </span>
      ),
      children: (
        <div className="space-y-4 py-2">
          <p className="text-sm text-ink-3">
            Choose how rows are ordered in the table.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={sortCol}
              onChange={(e) => setSortCol(e.target.value)}
              className="h-9 min-w-48 rounded-lg border border-rule bg-white px-3 text-sm text-ink"
            >
              <option value="">(Default order)</option>
              {base.columns.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </select>

            {sortCol && (
              <label className="flex items-center gap-2 text-sm text-ink cursor-pointer">
                <input
                  type="checkbox"
                  checked={sortDesc}
                  onChange={(e) => setSortDesc(e.target.checked)}
                  className="size-4 rounded border-rule text-ink"
                />
                <span>Highest first (Descending)</span>
              </label>
            )}
          </div>
        </div>
      ),
    },
    {
      key: "chart",
      label: (
        <span className="flex items-center gap-1.5">
          <BarChart3 className="size-4" /> Chart
        </span>
      ),
      children: (
        <div className="space-y-4 py-2">
          <p className="text-sm text-ink-3">
            Visualise the report data above the table.
          </p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { id: "none", label: "No chart" },
              { id: "bar", label: "Bar chart" },
              { id: "line", label: "Line chart" },
            ].map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setChart(opt.id as any)}
                className={`rounded-xl border p-4 text-center text-sm font-medium transition-colors ${
                  chart === opt.id
                    ? "border-ink bg-mint-2 font-semibold text-ink"
                    : "border-rule bg-white text-ink-2 hover:border-ink hover:text-ink"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      ),
    },
  ];

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={720}
      title={
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="size-5 text-sage-deep" />
          <span>{initial ? "Edit custom report" : "Customise report"}</span>
        </div>
      }
      footer={
        <div className="flex items-center justify-between border-t border-rule pt-4 mt-2">
          <div className="text-xs text-ink-3">
            Preview: <strong className="text-ink">{preview.rows.length}</strong>{" "}
            {groupBy ? "groups" : "rows"},{" "}
            <strong className="text-ink">{preview.columns.length}</strong>{" "}
            columns
          </div>
          <div className="flex items-center gap-2">
            <Button variant="default" onClick={onClose} disabled={isPending}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSave} disabled={isPending}>
              <Save className="mr-1.5 size-4" />
              {isPending
                ? "Saving..."
                : initial
                  ? "Update report"
                  : "Save custom report"}
            </Button>
          </div>
        </div>
      }
    >
      <div className="mt-3 space-y-4">
        {/* Name and Share header fields */}
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] items-end rounded-xl border border-rule bg-bench/30 p-3.5">
          <Field label="Report name">
            {(props) => (
              <Input
                {...props}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. High Value Customers"
                className="bg-white"
              />
            )}
          </Field>
          <label className="flex items-center gap-2 pb-2 text-sm text-ink-2 cursor-pointer">
            <input
              type="checkbox"
              checked={shared}
              onChange={(e) => setShared(e.target.checked)}
              className="size-4 rounded border-rule text-ink"
            />
            <span className="flex items-center gap-1 font-medium">
              <Share2 className="size-3.5 text-sage-deep" />
              Share with company
            </span>
          </label>
        </div>

        {/* Builder Tabs */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          className="report-builder-tabs"
        />
      </div>
    </Modal>
  );
}
