"use client";

import { Empty } from "@/src/platform/ui/sheet";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { isPending, useActivityFeed } from "../components/activity-feed";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Icon, listIcon } from "@/src/platform/ui/icons";
import { deleteActivity } from "../actions/customers";
import { makeFormat } from "@/src/platform/lib/format";
import { listName } from "@/src/platform/lib/labels";
import type { Activity, ListItem, Org } from "@/src/platform/lib/types";

export function Timeline({
  activities: given = [],
  today,
  org,
  kinds,
  outcomes,
}: {
  activities?: Activity[];
  today: string;
  org: Org;
  kinds: ListItem[];
  outcomes: ListItem[];
}) {
  const feed = useActivityFeed();
  const fmt = makeFormat(org);
  const activities = feed?.activities ?? given;
  if (activities.length === 0) {
    return <Empty compact icon="activity" title="Nothing logged yet">Everything your team records against this customer shows up here.</Empty>;
  }
  return (
    <ol className="divide-y divide-rule">
      {activities.map((a) => {
        const kind = listName(kinds, a.kind);
        return (
          <li key={a.id} className={`flex gap-3 py-3.5 ${isPending(a.id) ? "animate-reshape opacity-60" : ""}`}>
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-bench text-ink-2">
              {/* A switched-off kind is no longer on the list, so its code stands in for the picture too. */}
              <Icon name={listIcon(kinds.find((k) => k.code === a.kind) ?? { code: a.kind, icon: null })} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-meta text-ink-3">
                <span className="font-semibold text-ink-2">{kind}</span> ·{" "}
                {isPending(a.id) ? "Saving…" : fmt.whenLabel(a.occurredAt, today)} · {a.by.name}
                {a.outcome && <span className="font-semibold text-ink-2"> · {listName(outcomes, a.outcome)}</span>}
              </p>
              <p className="mt-0.5 whitespace-pre-line text-ink">{a.summary}</p>
            </div>
            {a.can.delete && (
              <ConfirmButton
                label={<span className="sr-only">Delete this {kind.toLowerCase()}</span>}
                icon={<Trash2 className="size-4" aria-hidden />}
                triggerVariant="quiet"
                triggerSize="sm"
                triggerClassName="!px-2 !text-ink-3 hover:!text-danger"
                title={`Delete this ${kind.toLowerCase()}?`}
                body="It will be removed from this customer's history for everyone. This can't be undone."
                confirmLabel="Delete"
                onConfirm={async () => {
                  const result = await deleteActivity(a.id);
                  if (!result.ok) {
                    toast.error(result.error);
                    return false;
                  }
                  toast.success("Deleted");
                }}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
