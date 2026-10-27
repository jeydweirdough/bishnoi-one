"use client";

import { Copy, Lock, Pencil, Share2, SlidersHorizontal, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ReportBuilderModal } from "./builder-modal";
import type { SavedReport } from "./custom";
import { deleteReport } from "./custom-actions";
import type { ReportData } from "./types";

interface Props {
  data: ReportData;
  app: string;
  base: string;
  savedReport?: SavedReport | null;
}

export function ReportCustomiseButton({ data, app, base, savedReport }: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [isDeleting, startDelete] = useTransition();
  const router = useRouter();

  const handleDelete = () => {
    if (!savedReport) return;
    if (!confirm(`Delete custom report "${savedReport.name}"? This cannot be undone.`)) {
      return;
    }
    startDelete(async () => {
      const res = await deleteReport(savedReport.id);
      if (!res.ok) {
        toast.error(res.error);
        return;
      }
      toast.success("Custom report deleted");
      const rootReports = base.slice(0, base.lastIndexOf("/"));
      router.push(rootReports);
      router.refresh();
    });
  };

  if (data.fixed) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-1.5 text-xs text-amber-900">
        <Lock className="size-3.5 shrink-0 text-amber-700" />
        <span>
          <strong>Fixed statutory report:</strong> calculations are controlled and cannot be customized.
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {savedReport ? (
        <>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-sage-deep/30 bg-mint-2 px-3 py-1 text-xs font-medium text-sage-deep">
            <Share2 className="size-3.5" />
            {savedReport.shared ? "Shared custom report" : "My custom report"}
            {!savedReport.mine && ` · by ${savedReport.owner}`}
          </span>
          {savedReport.mine ? (
            <>
              <Button size="sm" variant="default" onClick={() => setModalOpen(true)}>
                <Pencil className="mr-1.5 size-3.5" /> Edit definition
              </Button>
              <Button size="sm" variant="danger" onClick={handleDelete} disabled={isDeleting}>
                <Trash2 className="mr-1.5 size-3.5" /> {isDeleting ? "Deleting..." : "Delete"}
              </Button>
            </>
          ) : (
            <Button size="sm" variant="default" onClick={() => setModalOpen(true)}>
              <Copy className="mr-1.5 size-3.5" /> Save as copy
            </Button>
          )}
        </>
      ) : (
        <Button size="sm" variant="default" onClick={() => setModalOpen(true)}>
          <SlidersHorizontal className="mr-1.5 size-3.5 text-sage-deep" />
          Customise report
        </Button>
      )}

      {modalOpen && (
        <ReportBuilderModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          base={data}
          app={app}
          initial={savedReport}
          baseAddress={base}
        />
      )}
    </div>
  );
}
