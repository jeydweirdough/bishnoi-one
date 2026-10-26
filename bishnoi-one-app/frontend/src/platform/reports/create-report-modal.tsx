"use client";

import { Modal, Spin } from "antd";
import {
  FileText,
  Filter,
  Layers,
  Plus,
  SlidersHorizontal,
  Sparkles,
  ArrowRight,
  ChevronLeft,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ReportBuilderModal } from "./builder-modal";
import { fetchBaseReport } from "./custom-actions";
import type { ReportData, ReportInfo } from "./types";

interface Props {
  open: boolean;
  onClose: () => void;
  reports: ReportInfo[];
  baseAddress: string;
  app: string;
}

/**
 * Zoho-style "+ New Custom Report" creation wizard.
 * Step 1: Choose a base report template (grouped by category; excludes fixed statutory reports).
 * Step 2: Configure columns, filters, grouping/aggregations, charts and sharing in the guided builder.
 * Step 3: Save and immediately run with live data and computed totals.
 */
export function CreateReportModal({
  open,
  onClose,
  reports,
  baseAddress,
  app,
}: Props) {
  const router = useRouter();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [baseData, setBaseData] = useState<ReportData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [activeGroup, setActiveGroup] = useState<string>("All");

  // Non-fixed templates that can be customized
  const availableTemplates = useMemo(
    () => reports.filter((r) => !r.fixed),
    [reports],
  );

  const groups = useMemo(() => {
    const list = ["All", ...new Set(availableTemplates.map((r) => r.group))];
    return list;
  }, [availableTemplates]);

  const filteredTemplates = useMemo(() => {
    return availableTemplates.filter((r) => {
      const matchGroup = activeGroup === "All" || r.group === activeGroup;
      const matchSearch =
        !searchFilter.trim() ||
        r.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
        r.about.toLowerCase().includes(searchFilter.toLowerCase());
      return matchGroup && matchSearch;
    });
  }, [availableTemplates, activeGroup, searchFilter]);

  async function handleSelectTemplate(key: string) {
    setSelectedKey(key);
    setIsLoading(true);
    try {
      const res = await fetchBaseReport(app, key);
      if (!res.ok) {
        toast.error(res.error || "Failed to load base report definition.");
        setSelectedKey(null);
        return;
      }
      setBaseData(res.data);
    } catch {
      toast.error("Could not fetch report schema.");
      setSelectedKey(null);
    } finally {
      setIsLoading(false);
    }
  }

  function handleReset() {
    setSelectedKey(null);
    setBaseData(null);
  }

  function handleCloseAll() {
    handleReset();
    onClose();
  }

  // If a base report is chosen and loaded, show the full ReportBuilderModal
  if (baseData) {
    return (
      <ReportBuilderModal
        open={open}
        onClose={handleCloseAll}
        base={baseData}
        app={app}
        baseAddress={baseAddress}
        onSaved={(saved) => {
          handleCloseAll();
          router.push(
            `${baseAddress}/${saved.baseKey}?saved=${encodeURIComponent(saved.id)}`,
          );
        }}
      />
    );
  }

  return (
    <Modal
      open={open}
      onCancel={handleCloseAll}
      footer={null}
      width={840}
      title={
        <div className="flex items-center gap-2 text-ink">
          <div className="grid size-8 place-items-center rounded-lg bg-mint-2 text-sage-deep">
            <Sparkles className="size-4" />
          </div>
          <div>
            <h3 className="font-semibold text-ink text-base">
              Create New Custom Report
            </h3>
            <p className="text-xs text-ink-3 font-normal">
              Step 1 of 2: Select a base report template to customize with your own columns, filters, groupings, and totals.
            </p>
          </div>
        </div>
      }
    >
      <div className="space-y-4 py-3">
        {/* Search & Category Filter */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 max-w-lg">
            {groups.map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => setActiveGroup(g)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  activeGroup === g
                    ? "bg-ink text-white"
                    : "border border-rule text-ink-2 hover:border-ink hover:text-ink"
                }`}
              >
                {g}
              </button>
            ))}
          </div>

          <input
            type="search"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            placeholder="Search templates..."
            className="h-8 rounded-lg border border-rule bg-white px-3 text-xs outline-none focus:border-ink w-52"
          />
        </div>

        {/* Template Grid */}
        {isLoading ? (
          <div className="py-20 text-center space-y-3">
            <Spin size="large" />
            <p className="text-sm text-ink-2 font-medium">
              Loading report columns and calculation schema...
            </p>
          </div>
        ) : filteredTemplates.length === 0 ? (
          <div className="py-16 text-center text-ink-3 text-sm">
            No customizable templates found. Try clearing your search.
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-3 max-h-[28rem] overflow-y-auto pr-1">
            {filteredTemplates.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => handleSelectTemplate(t.key)}
                className="group relative flex flex-col justify-between rounded-xl border border-rule bg-white p-4 text-left transition-all hover:border-sage-deep hover:bg-mint-1/30 hover:shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="font-semibold text-sm text-ink group-hover:text-sage-deep transition-colors">
                      {t.title}
                    </span>
                    <span className="rounded bg-bench px-2 py-0.5 text-[10px] font-semibold text-ink-2 uppercase tracking-wider">
                      {t.group}
                    </span>
                  </div>
                  <p className="text-xs text-ink-3 line-clamp-2 leading-relaxed">
                    {t.about}
                  </p>
                </div>

                <div className="mt-3 flex items-center justify-between border-t border-rule/60 pt-2 text-meta text-ink-3">
                  <span>{t.dated ? "Date-filtered" : "Current state"}</span>
                  <span className="flex items-center gap-1 font-medium text-sage-deep opacity-0 group-hover:opacity-100 transition-opacity">
                    Customize <ArrowRight className="size-3" />
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-rule pt-3 text-xs text-ink-3">
          <span>
            {availableTemplates.length} customizable base templates available
          </span>
          <Button variant="default" onClick={handleCloseAll}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}
