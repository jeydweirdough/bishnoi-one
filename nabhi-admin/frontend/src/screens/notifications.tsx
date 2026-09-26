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
    { key: "critical", label: "Critical (Overdue / <7d)" },
    { key: "urgent", label: "Urgent (<15d)" },
    { key: "warning", label: "Warning (<60d)" },
    { key: "info", label: "Info (<90d)" },
  ];

  const filtered = initialNotifications.filter((n) => {
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
        return "bg-danger text-white font-bold";
      case "urgent":
        return "bg-eosin text-white font-semibold";
      case "warning":
        return "bg-hema text-white font-medium";
      default:
        return "border border-rule bg-bench text-ink-3";
    }
  };

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

      {/* Filter Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5 border-b border-rule pb-2">
        {severities.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setSelectedSeverity(s.key)}
            className={`rounded-[2px] px-3 py-1 text-meta font-medium transition-colors ${
              selectedSeverity === s.key
                ? "bg-hema text-white"
                : "text-ink-2 hover:bg-bench hover:text-ink"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <Sheet className="overflow-hidden">
        {filtered.length === 0 ? (
          <Empty title="No active notifications in this category" icon="notifications">
            All compliance deadlines and service tickets have been resolved or acknowledged.
          </Empty>
        ) : (
          <div className="divide-y divide-rule">
            {filtered.map((n) => (
              <div
                key={n.id}
                className={`p-4 transition-colors hover:bg-bench/20 ${!n.isRead ? "bg-hema-tint/15" : ""}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`inline-flex items-center rounded-[2px] px-1.5 py-0.5 text-stamp uppercase ${severityBadge(n.severity)}`}>
                        {n.severity}
                      </span>
                      <span className="inline-flex items-center rounded-[2px] border border-rule px-1.5 py-0.5 text-stamp uppercase text-ink-2">
                        {n.entityType}
                      </span>
                      {n.isAcknowledged && (
                        <span className="inline-flex items-center rounded-[2px] bg-bench px-1.5 py-0.5 text-stamp uppercase text-ink-3">
                          Acknowledged
                        </span>
                      )}
                      <CountdownBadge daysRemaining={n.daysRemaining} compact />
                    </div>

                    <h3 className="mt-1 text-base font-semibold text-ink">{n.title}</h3>
                    <p className="mt-0.5 text-sm text-ink-2">{n.message}</p>

                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-meta text-ink-3">
                      {n.dueDate && (
                        <span>
                          Target Expiry: <strong className="font-medium text-ink">{new Date(n.dueDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}</strong>
                        </span>
                      )}
                      <span>
                        Alert Triggered: {new Date(n.createdAt).toLocaleDateString("en-PH", { dateStyle: "short" })}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                    <Link
                      href={entityPath(n.entityType)}
                      className="rounded-[2px] border border-rule bg-sheet px-2.5 py-1 text-meta font-medium text-ink hover:bg-bench"
                    >
                      Open Record &rarr;
                    </Link>

                    {!n.isAcknowledged && (
                      <AsyncButton
                        variant="default"
                        size="sm"
                        onRun={async () => {
                          await acknowledgeNotification(n.id);
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
                      }}
                    >
                      Mark Resolved
                    </AsyncButton>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Sheet>
    </>
  );
}
