"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteTicket } from "@/src/actions/executive";
import { ExportButton } from "@/src/components/sheet-actions";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { TicketModal, TicketUpdateModal } from "@/src/components/executive-modals";
import type { OfficeTicket } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { RequestsStrip } from "@/src/components/overview-charts";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

// The same words as the request form's categories.
const CATEGORY_LABELS: Record<string, string> = {
  facilities: "Facilities and repairs",
  vip_logistics: "Guest transport",
  supplies: "Office supplies",
  boardroom: "Meeting rooms",
  courier_dispatch: "Courier and government liaison",
  it_security: "IT equipment and access cards",
  general: "Other",
};

export function TicketsScreen({ tickets: initialTickets }: { tickets: OfficeTicket[] }) {
  const [tickets, setTickets] = useState<OfficeTicket[]>(initialTickets);
  const [selectedStatus, setSelectedStatus] = useState<string>("active");
  const [modalTicket, setModalTicket] = useState<OfficeTicket | null | "new">(null);
  const [updateModalTicket, setUpdateModalTicket] = useState<OfficeTicket | null>(null);

  const statuses = [
    { key: "active", label: "Active" },
    { key: "open", label: "Open" },
    { key: "in_progress", label: "In progress" },
    { key: "pending_vendor", label: "Waiting on supplier" },
    { key: "resolved", label: "Resolved" },
    { key: "all", label: "All" },
  ];

  const filtered = tickets.filter((t) => {
    if (selectedStatus === "active") {
      return ["open", "in_progress", "pending_vendor"].includes(t.status);
    }
    if (selectedStatus === "resolved") {
      return ["resolved", "closed"].includes(t.status);
    }
    if (selectedStatus === "all") return true;
    return t.status === selectedStatus;
  });

  const priorityBadge = (p: OfficeTicket["priority"]) => {
    switch (p) {
      case "urgent":
        return "bg-danger-tint text-danger font-semibold";
      case "high":
        return "bg-eosin-tint text-eosin font-semibold";
      case "normal":
        return "bg-hema-tint text-hema font-medium";
      default:
        return "border border-rule text-ink-3";
    }
  };

  const totalOpen = tickets.filter((t) => ["open", "in_progress", "pending_vendor"].includes(t.status)).length;
  const lateCount = tickets.filter((t) => ["open", "in_progress", "pending_vendor"].includes(t.status) && (t.daysRemaining ?? 0) < 0).length;
  const resolvedCount = tickets.filter((t) => ["resolved", "closed"].includes(t.status)).length;

  return (
    <>
      <PageHeader
        title="Office requests"
        actions={
          <>
            <ExportButton kind="requests" />
            <Button variant="primary" onClick={() => setModalTicket("new")}>
              <Icon name="tickets" className="mr-1.5 size-4" />
              New office request
            </Button>
          </>
        }
      >
        Repairs, supplies, transport, courier and other requests to the administration office.
      </PageHeader>

      <RequestsStrip open={totalOpen} late={lateCount} resolved={resolvedCount} />

      {/* Filter Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        <div className="inline-flex flex-wrap rounded-[3px] border border-rule-strong bg-sheet p-0.5">
          {statuses.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setSelectedStatus(s.key)}
              className={`rounded-[2px] px-3 py-1 text-meta transition-colors ${
                selectedStatus === s.key
                  ? "bg-hema-tint font-semibold text-hema"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <Sheet>
        {filtered.length === 0 ? (
          <Empty title="No requests here" icon="tickets">
            Nothing is waiting on the administration office.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {filtered.map((t) => (
              <li
                key={t.id}
                className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-bench/40"
              >
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    <span className="font-mono text-stamp font-semibold text-ink-3">
                      {t.ticketNumber}
                    </span>
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-sm text-ink">{t.title}</span>
                      {/* Edit and delete sit with the record they act on. */}
                      <span className="inline-flex items-center">
                        <button
                          type="button"
                          onClick={() => setModalTicket(t)}
                          aria-label="Edit request"
                          title="Edit request"
                          className="inline-flex size-7 items-center justify-center rounded-[3px] text-ink-3 hover:bg-hema-tint hover:text-hema"
                        >
                          <Pencil className="size-3.5" aria-hidden />
                        </button>
                        <ConfirmButton
                          label={<span className="sr-only">Delete request</span>}
                          icon={<Trash2 className="size-3.5" aria-hidden />}
                          triggerTitle="Delete request"
                          triggerClassName="!size-7 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
                                              title={`Delete ${t.ticketNumber}?`}
                          body="This request and its updates are deleted. This cannot be undone."
                          confirmLabel="Delete request"
                          danger
                          triggerVariant="quiet"
                          triggerSize="sm"
                          onConfirm={async () => {
                          await deleteTicket(t.id);
                          setTickets((prev) => prev.filter((item) => item.id !== t.id));
                          }}
                          
                        />
                      </span>
                      <span className={`inline-block rounded-[2px] px-1.5 py-0.2 text-meta first-letter:uppercase ${priorityBadge(t.priority)}`}>
                        {t.priority}
                      </span>
                      <span className="inline-block rounded-[2px] border border-rule px-1.5 py-0.2 text-meta font-medium text-ink-3 first-letter:uppercase">
                        {CATEGORY_LABELS[t.category] ?? t.category.replace("_", " ")}
                      </span>
                    </div>

                    <p className="mt-1 text-sm text-ink-2">{t.description}</p>

                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-meta text-ink-3">
                      <span>Requested by: <strong className="font-medium text-ink-2">{t.requesterName}</strong></span>
                      {t.executiveSponsor && <span>Sponsor: <strong className="font-medium text-ink-2">{t.executiveSponsor}</strong></span>}
                      <span>Assigned to: <strong className="font-medium text-ink-2">{t.assignedTo || "Unassigned"}</strong></span>
                      {t.slaDueDate && (
                        <div className="flex items-center gap-1.5">
                          <span>Target date:</span>
                          <CountdownBadge daysRemaining={t.daysRemaining} urgencyTier={t.urgencyTier} compact />
                          <span className="tabular-nums">({new Date(t.slaDueDate).toLocaleDateString("en-PH", { dateStyle: "medium" })})</span>
                        </div>
                      )}
                    </div>

                    {t.resolutionNotes && (
                      <div className="mt-2 rounded-[2px] bg-bench/60 p-2 text-meta text-ink-2">
                        <strong className="font-semibold text-ink">Resolution: </strong>
                        {t.resolutionNotes}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <span className="inline-block rounded-[2px] border border-rule px-1.5 py-0.5 text-meta text-ink-3 first-letter:uppercase">
                    {t.status.replace("_", " ")}
                  </span>

                  <button
                    type="button"
                    onClick={() => setUpdateModalTicket(t)}
                    className="rounded-[3px] bg-hema-tint px-2.5 py-1 text-meta font-semibold text-hema hover:bg-hema/15"
                  >
                    Add update
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>

      {modalTicket !== null && (
        <TicketModal
          ticket={modalTicket === "new" ? null : modalTicket}
          onClose={() => setModalTicket(null)}
        />
      )}

      {updateModalTicket !== null && (
        <TicketUpdateModal
          ticket={updateModalTicket}
          onClose={() => setUpdateModalTicket(null)}
        />
      )}
    </>
  );
}
