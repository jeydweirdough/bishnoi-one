"use client";

import { Input, Select } from "antd";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Sheet } from "@/src/platform/ui/sheet";
import { addAssociationLabel, changeAssociationLabel, type AssociationLabel } from "../../actions/settings";

const KINDS = [
  { value: "company", label: "Customer" },
  { value: "contact", label: "Contact" },
  { value: "deal", label: "Deal" },
];
const kindName = (k: string) => KINDS.find((x) => x.value === k)?.label ?? k;

function Row({ l, onSaved }: { l: AssociationLabel; onSaved: (list: AssociationLabel[]) => void }) {
  const [name, setName] = useState(l.name);
  const [inverse, setInverse] = useState(l.inverseName);
  const [pending, start] = useTransition();
  const save = (change: Partial<{ name: string; inverseName: string; isActive: boolean }>) =>
    start(async () => {
      const r = await changeAssociationLabel(l.code, change);
      if (!r.ok) return void toast.error(r.error);
      onSaved(r.data);
    });
  return (
    <li className={`grid items-center gap-3 px-5 py-3 sm:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)_auto] ${l.isActive ? "" : "opacity-60"}`}>
      <span className="text-meta text-ink-3">
        {kindName(l.fromType)} → {kindName(l.toType)}
      </span>
      <Input value={name} onChange={(e) => setName(e.target.value)} onBlur={() => name.trim() && name !== l.name && save({ name: name.trim() })} aria-label="From the first side" />
      <Input value={inverse} onChange={(e) => setInverse(e.target.value)} onBlur={() => inverse.trim() && inverse !== l.inverseName && save({ inverseName: inverse.trim() })} aria-label="From the other side" />
      <span className="flex items-center gap-2">
        <span className="text-meta text-ink-3">{l.used} linked</span>
        <Button size="sm" variant="quiet" disabled={pending} onClick={() => save({ isActive: !l.isActive })}>
          {l.isActive ? "Switch off" : "Switch on"}
        </Button>
      </span>
    </li>
  );
}

/** Settings → Associations: what a link between two records can mean, read from each side. */
export function AssociationLabels({ initial }: { initial: AssociationLabel[] }) {
  const [list, setList] = useState(initial);
  const [from, setFrom] = useState("company");
  const [to, setTo] = useState("company");
  const [name, setName] = useState("");
  const [inverse, setInverse] = useState("");
  const [pending, start] = useTransition();
  function add() {
    start(async () => {
      const r = await addAssociationLabel({ fromType: from, toType: to, name: name.trim(), inverseName: inverse.trim() });
      if (!r.ok) return void toast.error(r.error);
      setList(r.data);
      setName("");
      setInverse("");
      toast.success("Label added");
    });
  }
  return (
    <div className="max-w-4xl space-y-4">
      <Sheet>
        <div className="grid gap-3 border-b border-rule px-5 py-2 text-meta font-medium text-ink-3 sm:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)_auto]">
          <span>Between</span>
          <span>Read from the first (a contact…)</span>
          <span>Read from the other (…their organization)</span>
          <span />
        </div>
        <ul className="divide-y divide-rule">
          {list.map((l) => (
            <Row key={l.code} l={l} onSaved={setList} />
          ))}
        </ul>
      </Sheet>
      <Sheet className="px-5 py-4">
        <p className="mb-3 font-semibold text-ink">A new kind of link</p>
        <div className="grid gap-3 sm:grid-cols-[9rem_9rem_minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
          <label className="block">
            <span className="mb-1 block text-meta text-ink-2">From</span>
            <Select className="w-full" value={from} onChange={setFrom} options={KINDS} />
          </label>
          <label className="block">
            <span className="mb-1 block text-meta text-ink-2">To</span>
            <Select className="w-full" value={to} onChange={setTo} options={KINDS} />
          </label>
          <label className="block">
            <span className="mb-1 block text-meta text-ink-2">Read from the first</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Trained at" maxLength={60} />
          </label>
          <label className="block">
            <span className="mb-1 block text-meta text-ink-2">Read from the other</span>
            <Input value={inverse} onChange={(e) => setInverse(e.target.value)} placeholder="e.g. Trained here" maxLength={60} />
          </label>
          <Button variant="primary" onClick={add} loading={pending} disabled={!name.trim() || !inverse.trim()}>
            Add
          </Button>
        </div>
      </Sheet>
    </div>
  );
}
