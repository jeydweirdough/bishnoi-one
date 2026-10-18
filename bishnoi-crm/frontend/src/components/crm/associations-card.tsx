"use client";

import { Modal } from "antd";
import { Combobox } from "@/src/platform/ui/pickers";
import { Link2, Plus, X } from "lucide-react";
import Link from "next/link";
import { useState, useTransition } from "react";
import { CustomerNotFound } from "../quick-add/customer-not-found";
import { toast } from "sonner";
import { Button, IconButton, TextButton } from "@/src/platform/ui/button";
import { FormError } from "@/src/platform/ui/field";
import { SectionTitle, Sheet, Empty } from "@/src/platform/ui/sheet";
import { addAssociation, findTargets, removeAssociation, type AssocKind, type Associations } from "../../actions/associations";

const HREF: Record<AssocKind, string> = { company: "/companies", contact: "/contacts", deal: "/deals" };
const WHICH: Record<AssocKind, string> = { company: "Which customer", contact: "Which contact", deal: "Which deal" };

/**
 * A record's associations (HubSpot's idea): the records linked to it, grouped
 * by what the link means from this side ("Works at", "People here"), each
 * group with + Add. Another division's record is named, and opened only by
 * those who reach it.
 */
export function AssociationsCard({ kind, id, data }: { kind: AssocKind; id: string; data: Associations }) {
  const [adding, setAdding] = useState<string | null>(null); // "label:side"
  const [other, setOther] = useState("");
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const picked = data.labels.find((l) => `${l.label}:${l.side}` === adding) ?? null;

  if (data.groups.length === 0 && data.labels.length === 0) return null;

  function search(otherType: AssocKind, q: string) {
    setTyped(q.trim());
    start(async () => setOptions((await findTargets(otherType, q)).map((t) => ({ value: t.id, label: t.hint ? `${t.name} · ${t.hint}` : t.name }))));
  }

  function open(key: string) {
    setAdding(key);
    setOther("");
    setError(null);
    const l = data.labels.find((x) => `${x.label}:${x.side}` === key);
    if (l) search(l.otherType, "");
  }

  function save() {
    if (!picked || !other) return setError("Pick who or what it's linked to.");
    start(async () => {
      const r = await addAssociation({ label: picked.label, side: picked.side, type: kind, id, otherId: other });
      if (!r.ok) return setError(r.fields ? Object.values(r.fields)[0] : r.error);
      toast.success("Linked");
      setAdding(null);
    });
  }

  function unlink(associationId: string) {
    start(async () => {
      const r = await removeAssociation(associationId);
      if (!r.ok) toast.error(r.error);
    });
  }

  const first = data.labels[0];
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle
        icon="customers"
        action={
          first && (
            <Button size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => open(`${first.label}:${first.side}`)}>
              Add
            </Button>
          )
        }
      >
        Associations
      </SectionTitle>
      {data.groups.length === 0 ? (
        <Empty compact icon="customers" title="No associations">Link where they work, the group it&apos;s part of, or who decides on a deal.</Empty>
      ) : (
        <div className="mt-1 space-y-3">
          {data.groups.map((g) => (
            <div key={`${g.label}:${g.side}`}>
              <div className="flex items-center justify-between">
                <p className="text-meta font-medium text-ink-2">
                  {g.name} <span className="text-ink-3">({g.items.length})</span>
                </p>
                {data.labels.some((l) => l.label === g.label && l.side === g.side) && (
                  <TextButton tone="muted" onClick={() => open(`${g.label}:${g.side}`)} aria-label={`Add to ${g.name}`}>
                    + Add
                  </TextButton>
                )}
              </div>
              <ul className="mt-1 divide-y divide-rule">
                {g.items.map((i) => (
                  <li key={i.type + i.id} className="flex items-center gap-2 py-1.5 text-sm">
                    <Link2 className="size-3.5 shrink-0 text-ink-3" aria-hidden />
                    {i.canOpen ? (
                      <Link href={`${HREF[i.type]}/${i.id}`} className="min-w-0 flex-1 truncate text-ink hover:underline">
                        {i.name}
                      </Link>
                    ) : (
                      <span className="min-w-0 flex-1 truncate text-ink">{i.name}</span>
                    )}
                    {i.canRemove && i.associationId && (
                      <IconButton tone="danger" size="sm" label={`Unlink ${i.name}`} onClick={() => unlink(i.associationId!)}>
                        <X className="size-3.5" aria-hidden />
                      </IconButton>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <Modal open={adding !== null} title="Link a record" onCancel={() => setAdding(null)} onOk={save} okText="Link" confirmLoading={pending} destroyOnHidden>
        <div className="space-y-4 pt-1">
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Relationship</span>
            <Combobox className="w-full" value={adding ?? undefined} onChange={(k) => open(k)} options={data.labels.map((l) => ({ value: `${l.label}:${l.side}`, label: l.name }))} />
          </label>
          {picked && (
            <label className="block">
              <span className="mb-1.5 block text-sm text-ink">{WHICH[picked.otherType]}</span>
              <Combobox
                className="w-full"
                value={other || undefined}
                onChange={setOther}
                options={options}
                showSearch={{ filterOption: false, onSearch: (q) => search(picked.otherType, q) }}
                placeholder="Type a name to search"
                notFoundContent={
                  picked.otherType === "company" ? (
                    <CustomerNotFound
                      typed={typed}
                      onAdded={(c) => {
                        setOptions((o) => [{ value: c.id, label: c.name }, ...o]);
                        setOther(c.id);
                      }}
                    />
                  ) : (
                    <p className="px-1 py-3 text-center text-meta text-ink-3">
                      {typed ? <>No {picked.otherType} called &ldquo;{typed}&rdquo; yet. </> : null}
                      {picked.otherType === "contact" ? "Contacts are added on a customer's page, under Contacts." : "Deals are added under Deals → New deal."}
                    </p>
                  )
                }
              />
            </label>
          )}
          <FormError message={error} />
        </div>
      </Modal>
    </Sheet>
  );
}
