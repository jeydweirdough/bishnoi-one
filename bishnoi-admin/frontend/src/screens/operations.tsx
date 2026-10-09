"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { useState } from "react";
import type { OperationsPath } from "@/src/actions/operations";
import { KINDS, type Cell, type Item } from "@/src/components/operations/kinds";
import { RecordForm } from "@/src/components/operations/record-form";
import { DueCell, Initials, RecordTable, Tag } from "@/src/components/record-table";
import { Button } from "@/src/platform/ui/button";
import { PageHeader } from "@/src/platform/ui/sheet";

type Can = { create: boolean; edit: boolean; delete: boolean };

/** One cell of the CRM's table, from what the list's description says it holds. */
export function CellView({ cell, href }: { cell: Cell; href?: string }) {
  switch (cell.type) {
    case "who":
      return (
        <span className="flex items-center gap-3">
          <Initials name={cell.name} filled={cell.filled} />
          <span className="min-w-0">
            {href ? (
              <Link href={href} className="block font-semibold text-ink hover:underline">
                {cell.name}
              </Link>
            ) : (
              <span className="block font-semibold text-ink">{cell.name}</span>
            )}
            {cell.sub && <span className="block text-[12.5px] text-ink-3">{cell.sub}</span>}
          </span>
        </span>
      );
    case "due":
      return <DueCell date={cell.date} days={cell.days} note={cell.note} />;
    case "tag":
      return (
        <Tag tone={cell.tone} dot={cell.dot}>
          {cell.text}
        </Tag>
      );
    case "money":
      return <span className="font-medium text-ink">{cell.text}</span>;
    default:
      return cell.text ? (
        <span className="block">
          {cell.text}
          {cell.sub && <span className="block text-[12.5px] text-ink-3">{cell.sub}</span>}
        </span>
      ) : (
        <span className="text-ink-3">—</span>
      );
  }
}

/**
 * One of the executive assistant's lists, as the CRM's customer list: its
 * header with the main button, then the table. A name opens its record page.
 */
export function OperationsScreen({ path, items: initialItems, can }: { path: OperationsPath; items: Item[]; can: Can }) {
  const kind = KINDS[path];
  const [items, setItems] = useState<Item[]>(initialItems);
  const [adding, setAdding] = useState(false);
  const total = `${items.length} ${items.length === 1 ? kind.one : kind.title.toLowerCase()}`;

  return (
    <>
      <PageHeader
        title={kind.title}
        actions={
          can.create && (
            <Button variant="primary" onClick={() => setAdding(true)}>
              <Plus className="size-4" aria-hidden />
              New {kind.one}
            </Button>
          )
        }
      >
        {total} · {kind.intro.charAt(0).toLowerCase() + kind.intro.slice(1)}
      </PageHeader>

      <RecordTable
        rows={items}
        searchLabel={`Search ${items.length} ${kind.title.toLowerCase()}`}
        search={kind.search}
        filter={kind.filter}
        emptyIcon={kind.icon}
        empty={{ title: `No ${kind.title.toLowerCase()} yet`, body: can.create ? `Add the first ${kind.one}.` : "They appear here once they're added." }}
        columns={kind.columns.map((c, n) => ({
          key: c.key,
          label: c.label,
          kind: c.kind,
          render: (row: Item) => <CellView cell={c.cell(row)} href={n === 0 ? `${kind.route}/${row.id}` : undefined} />,
        }))}
      />

      {adding && <RecordForm kind={kind} item={null} onClose={() => setAdding(false)} onSaved={(saved) => setItems((all) => [saved, ...all])} />}
    </>
  );
}
