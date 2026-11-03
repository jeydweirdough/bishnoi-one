"use client";

import type { ReactNode } from "react";
import { plural } from "../lib/format";
import type { Job } from "../lib/types";
import { Button } from "../ui/button";
import { ConfirmButton } from "../ui/confirm";
import { BulkBar, SelectionProvider, useBulkRun, useSelection } from "./selection";

export type BulkAction = {
  label: string;
  icon?: ReactNode;
  /** "Deleting", while it runs. */
  doing: string;
  /** "deleted": said after the count. */
  done: string;
  danger?: boolean;
  /** Asked first, for what can't be undone. */
  confirm?: string;
  /** A server action taking the ticked ids. */
  run: (ids: string[]) => Promise<{ ok: true; data: Job } | { ok: false; error: string }>;
};

export type BulkSetup = { noun: [string, string]; actions: BulkAction[] };

function Bar({ noun, actions }: BulkSetup) {
  const s = useSelection();
  const { run, running } = useBulkRun();
  const many = plural(s.ids.length, ...noun);
  const go = (a: BulkAction) => run({ doing: a.doing, did: (n) => `${plural(n, ...noun)} ${a.done}` }, a.run);
  return (
    <BulkBar noun={noun}>
      {actions.map((a) =>
        a.confirm ? (
          <ConfirmButton
            key={a.label}
            label={a.label}
            icon={a.icon}
            title={`${a.label} ${many}?`}
            body={a.confirm}
            confirmLabel={a.label}
            danger={a.danger}
            triggerSize="sm"
            triggerVariant={a.danger ? "danger" : "default"}
            disabled={running}
            onConfirm={async () => void (await go(a))}
          />
        ) : (
          <Button key={a.label} size="sm" icon={a.icon} disabled={running} onClick={() => void go(a)}>
            {a.label}
          </Button>
        ),
      )}
    </BulkBar>
  );
}

/**
 * Bulk actions for a list, the CRM's way, in one line for any screen: rows give SelectBox and SelectableRow, the
 * heading SelectAllBox, and the bar rises under the list. `items`: the rows that can be ticked on this page.
 */
export function BulkList({ items, noun, actions, children }: BulkSetup & { items: { id: string; name: string }[]; children: ReactNode }) {
  return (
    <SelectionProvider items={items}>
      {children}
      <Bar noun={noun} actions={actions} />
    </SelectionProvider>
  );
}
