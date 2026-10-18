"use client";

import { useState } from "react";
import { toast } from "sonner";
import { deleteTicket } from "@/src/actions/executive";
import { ExportButton } from "@/src/components/sheet-actions";
import { TicketModal, TicketUpdateModal } from "@/src/components/executive-modals";
import { DueCell, NameCell, RecordTable, Tag } from "@/src/components/record-table";
import type { OfficeTicket } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Icon } from "@/src/platform/ui/icons";
import { PageHeader } from "@/src/platform/ui/sheet";

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
const STATUS: Record<string, string> = { open: "Open", in_progress: "In progress", pending_vendor: "Waiting on supplier", resolved: "Resolved", closed: "Closed" };
const PRIORITY: Record<string, { text: string; tone: "bad" | "warn" | "outline" | "mute" }> = {
  urgent: { text: "Urgent", tone: "bad" },
  high: { text: "High", tone: "warn" },
  normal: { text: "Normal", tone: "outline" },
  low: { text: "Low", tone: "mute" },
};

/** What this person's role lets them do here; the API checks the same. */
type Can = { create: boolean; edit: boolean; delete: boolean };
const ALL: Can = { create: true, edit: true, delete: true };

const isOpen = (t: OfficeTicket) => ["open", "in_progress", "pending_vendor"].includes(t.status);

/** Requests to the administration office, as the CRM's list; Add update beside each open one. */
export function TicketsScreen({ tickets, can = ALL }: { tickets: OfficeTicket[]; can?: Can }) {
  const [gone, setGone] = useState<string[]>([]);
  const [modal, setModal] = useState<OfficeTicket | null | "new">(null);
  const [updating, setUpdating] = useState<OfficeTicket | null>(null);
  const rows = tickets.filter((t) => !gone.includes(t.id));
  const open = rows.filter(isOpen);
  const late = open.filter((t) => (t.daysRemaining ?? 0) < 0).length;

  return (
    <>
      <PageHeader
        title="Office requests"
        actions={
          <>
            <ExportButton kind="requests" />
            {can.create && (
              <Button variant="primary" onClick={() => setModal("new")}>
                <Icon name="tickets" className="size-4" />
                New office request
              </Button>
            )}
          </>
        }
      >
        {open.length} open{late ? `, ${late} past their target date` : ""} · repairs, supplies, transport, courier and other requests to the administration office
      </PageHeader>

      <RecordTable
        rows={rows}
        searchLabel={`Search ${rows.length} requests`}
        search={(t) => [t.ticketNumber, t.title, t.requesterName, t.assignedTo, t.description].join(" ")}
        filter={{
          label: "Show",
          options: { open: "Open", late: "Past target", resolved: "Resolved" },
          matches: (t, key) => (key === "open" ? isOpen(t) : key === "late" ? isOpen(t) && (t.daysRemaining ?? 0) < 0 : !isOpen(t)),
        }}
        emptyIcon="tickets"
        empty={{ title: "No requests", body: "Nothing is waiting on the administration office." }}
        rowTone={(t) => (isOpen(t) && (t.daysRemaining ?? 0) < 0 ? "bad" : null)}
        columns={[
          {
            key: "name",
            label: "Request",
            render: (t) => (
              <NameCell
                name={t.title}
                initials={t.ticketNumber.replace(/^[A-Z]+-?/, "").slice(-3)}
                filled={isOpen(t) && (t.priority === "urgent" || t.priority === "high")}
                sub={`${t.ticketNumber} · ${CATEGORY_LABELS[t.category] ?? t.category.replace("_", " ")}`}
                what="request"
                onEdit={can.edit ? () => setModal(t) : undefined}
                onDelete={
                  can.delete
                    ? async () => {
                        const r = await deleteTicket(t.id);
                        if (!r.ok) {
                          toast.error(r.error);
                          return false;
                        }
                        setGone((g) => [...g, t.id]);
                        toast.success("Request deleted", { description: t.ticketNumber });
                      }
                    : undefined
                }
              />
            ),
          },
          { key: "who", label: "Asked by", kind: "hide-sm", render: (t) => <span className="block">{t.requesterName}<span className="block text-[12.5px] text-ink-3">{t.assignedTo ? `with ${t.assignedTo}` : "not assigned"}</span></span> },
          { key: "priority", label: "Priority", render: (t) => <Tag tone={PRIORITY[t.priority]?.tone ?? "outline"}>{PRIORITY[t.priority]?.text ?? t.priority}</Tag> },
          { key: "target", label: "Target date", render: (t) => (isOpen(t) ? <DueCell date={t.slaDueDate} days={t.daysRemaining} /> : <span className="text-ink-3">Done</span>) },
          { key: "status", label: "Status", render: (t) => <Tag tone={isOpen(t) ? (t.status === "pending_vendor" ? "info" : "warn") : "good"} dot>{STATUS[t.status] ?? t.status}</Tag> },
          {
            key: "update",
            label: "",
            render: (t) =>
              can.edit && isOpen(t) ? (
                <Button size="sm" onClick={() => setUpdating(t)}>
                  Add update
                </Button>
              ) : null,
          },
        ]}
      />

      {modal !== null && <TicketModal ticket={modal === "new" ? null : modal} onClose={() => setModal(null)} />}
      {updating && <TicketUpdateModal ticket={updating} onClose={() => setUpdating(null)} />}
    </>
  );
}
