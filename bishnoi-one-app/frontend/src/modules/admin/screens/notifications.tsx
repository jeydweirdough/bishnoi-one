"use client";

import Link from "next/link";
import { useState } from "react";
import {
  acknowledgeNotification,
  resolveNotification,
  syncNotificationsAction,
} from "@/src/modules/admin/actions/executive";
import { CountdownBadge } from "@/src/modules/admin/components/countdown-badge";
import type { ExecutiveNotification } from "@/src/modules/admin/platform/lib/types";
import { AsyncButton } from "@/src/modules/admin/platform/ui/async-button";
import { Figure } from "@/src/modules/admin/platform/ui/figure";
import { Icon } from "@/src/modules/admin/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/modules/admin/platform/ui/sheet";

/** What this person's role lets them do here; the API checks the same. */
type Can = { acknowledge: boolean; resolve: boolean };

export function NotificationsScreen({
  notifications: initialNotifications,
  can = { acknowledge: true, resolve: true },
}: {
  notifications: ExecutiveNotification[];
  can?: Can;
}) {
  const [notifications, setNotifications] = useState<ExecutiveNotification[]>(initialNotifications);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");

  const severities = [
    { key: "all", label: "All" },
    { key: "critical", label: "Overdue or within 7 days" },
    { key: "urgent", label: "Within 15 days" },
    { key: "warning", label: "Within 60 days" },
    { key: "info", label: "Within 90 days" },
  ];

  const filtered = notifications.filter((n) => {
    if (selectedSeverity === "all") return true;
    return n.severity === selectedSeverity;
  });

  const entityPath = (type: string) => {
    switch (type) {
      case "permit":
        return "/admin/permits";
      case "immigration":
        return "/admin/immigration";
      case "document":
        return "/admin/documents";
      case "property":
        return "/admin/properties";
      case "ticket":
        return "/admin/tickets";
      case "vehicle_registration":
      case "vehicle_insurance":
      case "vehicle_pms":
        return "/admin/vehicles";
      case "travel":
        return "/admin/travel";
      default:
        return "/";
    }
  };

  const severityBadge = (s: ExecutiveNotification["severity"]) => {
    switch (s) {
      case "critical":
        return "bg-danger-tint text-danger font-semibold";
      case "urgent":
        return "bg-eosin-tint text-eosin font-semibold";
      case "warning":
        return "bg-hema-tint text-hema font-medium";
      default:
        return "border border-rule text-ink-3";
    }
  };

  const totalActive = notifications.filter((n) => !n.isResolved).length;
  const criticalCount = notifications.filter((n) => (n.severity === "critical" || n.severity === "urgent") && !n.isResolved).length;
  const unreadCount = notifications.filter((n) => !n.isRead && !n.isResolved).length;

  return (
    <>
      <PageHeader
        title="Renewal alerts"
        actions={
          <AsyncButton
            variant="default"
            onRun={async () => {
              await syncNotificationsAction();
            }}
          >
            <Icon name="history" className="mr-1.5 size-4" />
            Check for new alerts
          </AsyncButton>
        }
      >
        Alerts raised 90, 60, 30, 15 and 7 days before a permit, document or lease expires, and again when it's overdue.
      </PageHeader>

      {/* Top Figure KPI Metrics Strip */}
      <Sheet className="mb-5 grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Figure label="Active alerts" value={totalActive} />
        <Figure label="Within 15 days or overdue" value={criticalCount} flag={criticalCount > 0} />
        <Figure label="Unread" value={unreadCount} flag={unreadCount > 0} />
      </Sheet>

      {/* Filter Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        <div className="inline-flex flex-wrap rounded-[12px] border border-rule-strong bg-sheet p-0.5">
          {severities.map((s) => (
            <button suppressHydrationWarning
              key={s.key}
              type="button"
              onClick={() => setSelectedSeverity(s.key)}
              className={`rounded-full px-3 py-1 text-meta transition-colors ${
                selectedSeverity === s.key
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
          <Empty title="No alerts here" icon="notifications">
            Everything in this range has been renewed or acknowledged.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {filtered.map((n) => (
              <li
                key={n.id}
                className={`flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-bench/40 ${
                  !n.isRead ? "bg-hema-tint/15" : ""
                }`}
              >
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    <CountdownBadge daysRemaining={n.daysRemaining} compact />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-sm text-ink">{n.title}</span>
                      <span className={`inline-block rounded-full px-1.5 py-0.2 text-meta first-letter:uppercase ${severityBadge(n.severity)}`}>
                        {n.severity}
                      </span>
                      <span className="rounded-full border border-rule px-1.5 py-0.2 text-meta font-medium text-ink-3">
                        {n.entityType}
                      </span>
                      {n.isAcknowledged && (
                        <span className="rounded-full bg-bench px-1.5 py-0.2 text-meta text-ink-3">
                          Acknowledged
                        </span>
                      )}
                    </div>

                    <p className="mt-1 text-sm text-ink-2">{n.message}</p>

                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-meta text-ink-3">
                      {n.dueDate && (
                        <span>
                          Target Expiry: <strong className="font-medium text-ink-2">{new Date(n.dueDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}</strong>
                        </span>
                      )}
                      <span>
                        Alert Triggered: {new Date(n.createdAt).toLocaleDateString("en-PH", { dateStyle: "short" })}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <Link
                    href={entityPath(n.entityType)}
                    className="rounded-[12px] border border-rule-strong bg-sheet px-2.5 py-1 text-meta font-medium text-ink hover:border-control"
                  >
                    Open Record &rarr;
                  </Link>

                  {can.acknowledge && !n.isAcknowledged && (
                    <AsyncButton
                      variant="default"
                      size="sm"
                      onRun={async () => {
                        await acknowledgeNotification(n.id);
                        setNotifications((prev) =>
                          prev.map((item) => (item.id === n.id ? { ...item, isAcknowledged: true } : item))
                        );
                      }}
                    >
                      Acknowledge
                    </AsyncButton>
                  )}

                  {can.resolve && (
                    <AsyncButton
                      variant="quiet"
                      size="sm"
                      onRun={async () => {
                        await resolveNotification(n.id);
                        setNotifications((prev) =>
                          prev.map((item) => (item.id === n.id ? { ...item, isResolved: true } : item))
                        );
                      }}
                    >
                      Mark Resolved
                    </AsyncButton>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
