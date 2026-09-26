"use client";

import Link from "next/link";
import { useState } from "react";
import {
  acknowledgeNotification,
  resolveNotification,
  syncNotificationsAction,
} from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import type { ExecutiveNotification } from "@/src/platform/lib/types";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { Figure } from "@/src/platform/ui/figure";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function NotificationsScreen({
  notifications: initialNotifications,
}: {
  notifications: ExecutiveNotification[];
}) {
  const [notifications, setNotifications] = useState<ExecutiveNotification[]>(initialNotifications);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");

  const severities = [
    { key: "all", label: "All Alerts" },
    { key: "critical", label: "Critical (<7d / Overdue)" },
    { key: "urgent", label: "Urgent (<15d)" },
    { key: "warning", label: "Warning (<60d)" },
    { key: "info", label: "Notice (<90d)" },
  ];

  const filtered = notifications.filter((n) => {
    if (selectedSeverity === "all") return true;
    return n.severity === selectedSeverity;
  });

  const entityPath = (type: string) => {
    switch (type) {
      case "permit":
        return "/permits";
      case "immigration":
        return "/immigration";
      case "document":
        return "/documents";
      case "property":
        return "/properties";
      case "ticket":
        return "/tickets";
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
        title="Proactive Renewal Alerts & Notification Matrix"
        crumbs={[{ href: "/", label: "Executive Admin" }, { href: "/notifications", label: "Alerts" }]}
        actions={
          <AsyncButton
            variant="default"
            onRun={async () => {
              await syncNotificationsAction();
            }}
          >
            <Icon name="history" className="mr-1.5 size-4" />
            Re-scan Expiration Deadlines
          </AsyncButton>
        }
      >
        Automated multi-tier notification engine (90, 60, 30, 15, 7 days and overdue escalation) for Executive Administrators and Assistants.
      </PageHeader>

      {/* Top Figure KPI Metrics Strip */}
      <Sheet className="mb-5 grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Figure label="Active Expiration Alerts" value={totalActive} />
        <Figure label="Critical & Urgent Attention" value={criticalCount} flag={criticalCount > 0} />
        <Figure label="Unread Notifications" value={unreadCount} flag={unreadCount > 0} />
      </Sheet>

      {/* Filter Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        <div className="inline-flex flex-wrap rounded-[3px] border border-rule-strong bg-sheet p-0.5">
          {severities.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setSelectedSeverity(s.key)}
              className={`rounded-[2px] px-3 py-1 text-meta transition-colors ${
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
          <Empty title="No active notifications in this category" icon="notifications">
            All compliance deadlines and service tickets have been resolved or acknowledged.
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
                      <span className={`inline-flex items-center rounded-[2px] px-1.5 py-0.2 text-stamp uppercase ${severityBadge(n.severity)}`}>
                        {n.severity}
                      </span>
                      <span className="rounded-[2px] border border-rule px-1.5 py-0.2 text-stamp font-medium text-ink-3 uppercase">
                        {n.entityType}
                      </span>
                      {n.isAcknowledged && (
                        <span className="rounded-[2px] bg-bench px-1.5 py-0.2 text-stamp uppercase text-ink-3">
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
                    className="rounded-[3px] border border-rule-strong bg-sheet px-2.5 py-1 text-meta font-medium text-ink hover:border-control"
                  >
                    Open Record &rarr;
                  </Link>

                  {!n.isAcknowledged && (
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
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
