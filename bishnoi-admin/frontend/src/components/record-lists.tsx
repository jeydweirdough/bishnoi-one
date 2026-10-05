"use client";

import { useState } from "react";
import { ACTIVITY_ICONS } from "@/src/platform/ui/icons";
import { saveRecordList } from "../actions/admin";
import type { ListKind, ListSettings } from "@/src/platform/lib/types";
import { ListEditor, listDetail, listRows, type ListRow } from "@/src/platform/ui/list-editor";
import { PickList, type PickItem } from "@/src/platform/ui/pick-list";

// Settings → Lists: pick one list, then edit only that one. Each keeps what has
// been typed into it while another is open, the same as Settings → Orders.

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

// What switching a choice off means, in the words of the records that carry it.
const NOTE: Record<ListKind, string> = {
  customer_kind: "A customer already filed under a switched-off kind keeps it; nobody can pick it for a new one.",
  activity_kind: "Calls and visits already logged this way keep it; nobody can log a new one under it.",
  outcome: "Activities already marked with it keep it; nobody can pick it again.",
};

const SAVED: Record<ListKind, string> = {
  customer_kind: "Your people see the new words on their next customer.",
  activity_kind: "Your people see the new words the next time they log something.",
  outcome: "Your people see the new words the next time they log a call or visit.",
};

export function RecordListsEditor({ data }: { data: ListSettings }) {
  const [view, setView] = useState<ListKind>(data.kinds[0]?.kind ?? "customer_kind");
  const [lists, setLists] = useState<Partial<Record<ListKind, ListRow[]>>>({});

  const dirty = (kind: ListKind) => lists[kind] !== undefined && !same(lists[kind], listRows(data.lists[kind]));
  const setList = (kind: ListKind) => (rows: ListRow[] | undefined) => setLists((all) => ({ ...all, [kind]: rows }));

  const items: PickItem[] = data.kinds.map((k) => ({
    key: k.kind,
    label: k.label,
    detail: listDetail(data.lists[k.kind]),
    unsaved: dirty(k.kind),
  }));
  const kind = data.kinds.find((k) => k.kind === view) ?? data.kinds[0];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
      <PickList title="Your lists" icon="lists" items={items} selected={view} onSelect={(key) => setView(key as ListKind)} />
      {kind && (
        <ListEditor
          key={kind.kind}
          icon="lists"
          label={kind.label}
          hint={kind.hint}
          note={NOTE[kind.kind]}
          savedNote={SAVED[kind.kind]}
          icons={kind.hasIcons ? ACTIVITY_ICONS : undefined}
          required={kind.required}
          rows={lists[kind.kind] ?? listRows(data.lists[kind.kind])}
          dirty={dirty(kind.kind)}
          setRows={setList(kind.kind)}
          onSave={(rows) => saveRecordList(kind.kind, rows)}
        />
      )}
    </div>
  );
}
