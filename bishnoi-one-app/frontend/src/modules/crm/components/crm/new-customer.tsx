"use client";

import { Input } from "@/src/platform/ui/field";
import { Modal } from "antd";
import { Combobox } from "@/src/platform/ui/pickers";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { Button } from "@/src/platform/ui/button";
import type { Assignable, CustomerType } from "@/src/platform/lib/types";
import { addCustomerChoices } from "@/src/modules/crm/actions/crm";
import { forTeam } from "@/src/modules/crm/components/extra/teams";
import { Lookalikes } from "@/src/modules/crm/components/crm/lookalikes";

type Choices = { people: Assignable[]; types: CustomerType[] };

/** Where the form goes next: the division (as a team), the type and the name chosen here. */
/** What opens once the customer is saved: their new quote or deal. */
export type Then = "quote" | "deal" | null;

function formHref(team: string, kind: string, name: string, then: Then) {
  const q = new URLSearchParams({ team, type: kind });
  if (name.trim()) q.set("name", name.trim());
  if (then) q.set("then", then);
  return `/crm/companies/new?${q}`;
}

/**
 * The questions that shape the rest of the form: which division (only for
 * someone who adds to more than one), what kind of customer, and the name.
 * Customers like it already in the CRM are shown, never refused: one hospital
 * can be a customer of several divisions.
 */
export function CustomerStart({
  choices,
  kind: fixedKind,
  initialName = "",
  then = null,
  onDone,
}: {
  choices: Choices;
  /** Asked for one kind only ("Add a doctor"): the type isn't asked. */
  kind?: string;
  initialName?: string;
  then?: Then;
  onDone?: () => void;
}) {
  const router = useRouter();
  const teams = [...new Map(choices.people.filter((p) => p.team).map((p) => [p.team!.id, p.team!.name])).entries()].map(([id, name]) => ({ id, name }));
  const mine = choices.people.find((p) => p.isMe)?.team?.id ?? teams[0]?.id ?? "";
  const [team, setTeam] = useState(mine);
  const offered = choices.types.filter((t) => t.isActive && forTeam(t, team || null));
  const [kind, setKind] = useState(fixedKind ?? "");
  const [name, setName] = useState(initialName);
  const picked = fixedKind ?? (offered.some((t) => t.code === kind) ? kind : "");
  const ready = Boolean(picked && name.trim());

  function go() {
    if (!ready) return;
    onDone?.();
    router.push(formHref(team, picked, name, then));
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        go();
      }}
    >
      {teams.length > 1 && (
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Division</span>
          <Combobox
            className="w-full"
            value={team || undefined}
            onChange={(v) => setTeam(v)}
            options={teams.map((t) => ({ value: t.id, label: t.name }))}
            showSearch={{ optionFilterProp: "label" }}
          />
        </label>
      )}
      {!fixedKind && (
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Customer type</span>
          <Combobox
            className="w-full"
            size="large"
            value={picked || undefined}
            onChange={(v) => setKind(v)}
            options={offered.map((t) => ({ value: t.code, label: t.name }))}
            showSearch={{ optionFilterProp: "label" }}
            placeholder="Type to search"
            autoFocus
          />
        </label>
      )}
      <label className="block">
        <span className="mb-1.5 block text-sm text-ink">Name</span>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Write it the way it should read in the list" autoFocus={Boolean(fixedKind)} />
      </label>
      <Lookalikes name={name} phone="" email="" />
      <div className="flex justify-end gap-2 pt-1">
        {onDone && <Button onClick={onDone}>Cancel</Button>}
        <Button type="submit" variant="primary" disabled={!ready}>
          Continue
        </Button>
      </div>
    </form>
  );
}

/** "Add customer": the first questions in a pop-up, then the form made for the answers. */
export function NewCustomerButton({
  label = "Add customer",
  variant = "primary",
  kind,
  icon = true,
}: {
  label?: string;
  variant?: "primary" | "default";
  kind?: string;
  icon?: boolean;
}) {
  const [choices, setChoices] = useState<Choices | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, start] = useTransition();

  function show() {
    setOpen(true);
    if (!choices) start(async () => setChoices(await addCustomerChoices()));
  }

  return (
    <>
      <Button variant={variant} icon={icon ? <Plus className="size-4" aria-hidden /> : undefined} onClick={show} loading={loading} aria-haspopup="dialog">
        {label}
      </Button>
      <Modal open={open && Boolean(choices)} title={label} onCancel={() => setOpen(false)} footer={null} width={480} destroyOnHidden>
        {choices && <CustomerStart choices={choices} kind={kind} onDone={() => setOpen(false)} />}
      </Modal>
    </>
  );
}

/** The same dialog, opened by something else (a search that found nobody), with the name already typed. */
export function AddCustomerDialog({ open, onClose, kind, initialName, title = "Add customer" }: { open: boolean; onClose: () => void; kind?: string; initialName: string; title?: string }) {
  const [choices, setChoices] = useState<Choices | null>(null);
  const [, start] = useTransition();
  useEffect(() => {
    if (open && !choices) start(async () => setChoices(await addCustomerChoices()));
  }, [open, choices]);
  return (
    <Modal open={open && Boolean(choices)} title={title} onCancel={onClose} footer={null} width={480} destroyOnHidden>
      {choices && <CustomerStart choices={choices} kind={kind} initialName={initialName} onDone={onClose} />}
    </Modal>
  );
}
