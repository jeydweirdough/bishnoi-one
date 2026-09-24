"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, Input, Select } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import type { CustomerType, CustomerTypeColor } from "@/src/platform/lib/types";
import { deleteCustomerType, saveCustomerType, type CustomerTypeChange } from "../../actions/admin";
import { StatusTag, TYPE_COLORS } from "../crm/words";

const COLORS = Object.entries(TYPE_COLORS) as [CustomerTypeColor, { label: string }][];

/** The customer types: add, rename, recolour, reorder, switch off, delete an unused one. */
export function CustomerTypesEditor({ types }: { types: CustomerType[] }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [name, setName] = useState("");
  const [color, setColor] = useState<CustomerTypeColor>("gray");
  const [fields, setFields] = useState<Record<string, string>>({});

  function save(code: string | null, change: CustomerTypeChange, done: string) {
    start(async () => {
      const result = await saveCustomerType(code, change);
      if (!result.ok) {
        if (code) toast.error(result.fields?.name ?? result.error);
        else setFields(result.fields ?? { name: result.error });
        return;
      }
      if (!code) {
        setName("");
        setFields({});
      }
      toast.success(done);
      router.refresh();
    });
  }

  // Moving swaps places with the neighbour, so the order stays 0, 1, 2...
  function move(i: number, by: -1 | 1) {
    const a = types[i];
    const b = types[i + by];
    start(async () => {
      const first = await saveCustomerType(a.code, { sortOrder: i + by });
      const second = first.ok ? await saveCustomerType(b.code, { sortOrder: i }) : first;
      if (!second.ok) toast.error(second.error);
      router.refresh();
    });
  }

  return (
    <div className="space-y-5">
      <Sheet className="px-5 py-4">
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            save(null, { name: name.trim(), color }, `${name.trim()} added`);
          }}
          className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_auto]"
        >
          <Field label="New type" error={fields.name}>
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Key account" />}
          </Field>
          <Field label="Colour">
            {(p) => (
              <Select {...p} value={color} onChange={(e) => setColor(e.target.value as CustomerTypeColor)}>
                {COLORS.map(([value, c]) => (
                  <option key={value} value={value}>
                    {c.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Button type="submit" variant="primary" loading={pending} disabled={!name.trim()}>
            Add type
          </Button>
        </form>
      </Sheet>

      <Sheet>
        <ul className="divide-y divide-rule">
          {types.map((t, i) => (
            <TypeRow
              key={t.code}
              type={t}
              first={i === 0}
              last={i === types.length - 1}
              pending={pending}
              onSave={(change, done) => save(t.code, change, done)}
              onMove={(by) => move(i, by)}
              onDeleted={() => router.refresh()}
            />
          ))}
        </ul>
      </Sheet>
    </div>
  );
}

function TypeRow({
  type,
  first,
  last,
  pending,
  onSave,
  onMove,
  onDeleted,
}: {
  type: CustomerType;
  first: boolean;
  last: boolean;
  pending: boolean;
  onSave: (change: CustomerTypeChange, done: string) => void;
  onMove: (by: -1 | 1) => void;
  onDeleted: () => void;
}) {
  const [name, setName] = useState(type.name);
  return (
    <li className={`flex flex-wrap items-center gap-3 px-5 py-3 ${type.isActive ? "" : "bg-bench/50"}`}>
      <span className="flex flex-col">
        <button type="button" disabled={first || pending} onClick={() => onMove(-1)} className="text-ink-3 hover:text-hema disabled:opacity-30" aria-label={`Move ${type.name} up`}>
          <ArrowUp className="size-3.5" aria-hidden />
        </button>
        <button type="button" disabled={last || pending} onClick={() => onMove(1)} className="text-ink-3 hover:text-hema disabled:opacity-30" aria-label={`Move ${type.name} down`}>
          <ArrowDown className="size-3.5" aria-hidden />
        </button>
      </span>
      <span className="w-32">
        <StatusTag status={type.code} types={[type]} />
      </span>
      <input
        aria-label={`Name of ${type.name}`}
        value={name}
        onChange={(e) => setName(e.target.value)}
        onBlur={() => name.trim() && name.trim() !== type.name && onSave({ name: name.trim() }, "Renamed")}
        className="h-9 min-w-40 flex-1 border-0 border-b border-control bg-transparent px-0 text-sm focus:border-hema focus:outline-none"
      />
      <select
        aria-label={`Colour of ${type.name}`}
        value={type.color}
        onChange={(e) => onSave({ color: e.target.value as CustomerTypeColor }, "Colour changed")}
        className="h-9 border-0 border-b border-control bg-transparent text-sm focus:border-hema focus:outline-none"
      >
        {COLORS.map(([value, c]) => (
          <option key={value} value={value}>
            {c.label}
          </option>
        ))}
      </select>
      <span className="w-28 text-meta text-ink-3">
        {type.companies} {type.companies === 1 ? "customer" : "customers"}
      </span>
      <Button size="sm" variant="quiet" disabled={pending} onClick={() => onSave({ isActive: !type.isActive }, type.isActive ? `${type.name} switched off` : `${type.name} switched on`)}>
        {type.isActive ? "Switch off" : "Switch on"}
      </Button>
      {type.companies === 0 && (
        <ConfirmButton
          label="Delete"
          triggerSize="sm"
          title={`Delete ${type.name}?`}
          body="No customer is this type, so nothing else changes."
          confirmLabel="Delete type"
          onConfirm={async () => {
            const result = await deleteCustomerType(type.code);
            if (!result.ok) {
              toast.error(result.error);
              return false;
            }
            toast.success(`${type.name} deleted`);
            onDeleted();
          }}
        />
      )}
    </li>
  );
}
