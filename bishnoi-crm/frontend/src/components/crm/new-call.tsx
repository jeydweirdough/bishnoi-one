"use client";

import { Modal } from "antd";
import { Combobox } from "@/src/platform/ui/pickers";
import { DateTimeField } from "@/src/platform/ui/pickers";
import dayjs, { type Dayjs } from "dayjs";
import { PhoneCall } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { FieldRow } from "@/src/platform/ui/dialog";
import { FormError, Input, Textarea } from "@/src/platform/ui/field";
import { callChoices, createActivity } from "../../actions/crm";
import { findCustomers } from "../../actions/deals";
import { CustomerNotFound } from "../quick-add/customer-not-found";

type Option = { value: string; label: string };

/**
 * Calendar → New call: plan a call or visit the way a rep thinks of it. Who
 * with, when, what it's for, and which products to bring up. Once it's done,
 * ticking it off asks what came of it.
 */
export function NewCallButton({ customer, variant = "primary" }: { customer?: { id: string; name: string }; variant?: "primary" | "default" }) {
  const [open, setOpen] = useState(false);
  const [products, setProducts] = useState<Option[] | null>(null);
  const [customers, setCustomers] = useState<Option[]>(customer ? [{ value: customer.id, label: customer.name }] : []);
  const [companyId, setCompanyId] = useState(customer?.id ?? "");
  const [when, setWhen] = useState<Dayjs | null>(dayjs().add(1, "day").hour(9).minute(0).second(0));
  const [objective, setObjective] = useState("");
  const [link, setLink] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const [typed, setTyped] = useState("");

  function show() {
    setOpen(true);
    if (!products) start(async () => setProducts((await callChoices()).products));
    if (!customer) search("");
  }

  function search(q: string) {
    setTyped(q.trim());
    start(async () => setCustomers((await findCustomers(q)).map((c) => ({ value: c.id, label: c.city ? `${c.name} · ${c.city}` : c.name }))));
  }

  function save() {
    if (!companyId || !when || !objective.trim()) return setError("Customer, date and time, and objective are required.");
    start(async () => {
      const r = await createActivity({
        kind: "meeting",
        subject: objective.trim(),
        objective: objective.trim(),
        meetingLink: link.trim() || null,
        products: picked,
        body: null,
        at: when.format("YYYY-MM-DDTHH:mm"),
        companyId,
        contactId: null,
        durationMinutes: null,
        direction: null,
        ownerId: null,
      });
      if (!r.ok) return setError(r.error);
      toast.success("Call scheduled", { description: `${when.format("ddd D MMM, h:mm A")}: ${objective.trim()}` });
      setOpen(false);
      setObjective("");
      setLink("");
      setPicked([]);
      setError(null);
    });
  }

  return (
    <>
      <Button variant={variant} icon={<PhoneCall className="size-4" aria-hidden />} onClick={show}>
        New call
      </Button>
      <Modal open={open} title="New call" onCancel={() => setOpen(false)} onOk={save} okText="Schedule call" confirmLoading={pending} width={600} destroyOnHidden>
        <div className="space-y-4">
          {/* Who and when, side by side; then what it's for. */}
          <FieldRow>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Customer</span>
            <Combobox
              className="w-full"
              value={companyId || undefined}
              onChange={setCompanyId}
              options={customers}
              disabled={Boolean(customer)}
              showSearch={{ filterOption: false, onSearch: search }}
              placeholder="Type a customer's name"
              notFoundContent={
                <CustomerNotFound
                  typed={typed}
                  loading={pending}
                  onAdded={(c) => {
                    setCustomers((o) => [{ value: c.id, label: c.name }, ...o]);
                    setCompanyId(c.id);
                  }}
                />
              }
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Date and time</span>
            <DateTimeField value={when ? when.format("YYYY-MM-DDTHH:mm") : ""} onChange={(v) => setWhen(v ? dayjs(v) : null)} />
          </label>
          </FieldRow>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Objective</span>
            <Input value={objective} onChange={(e) => setObjective(e.target.value)} maxLength={300} placeholder="e.g. Get Onco One on their formulary" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">
              Video call link <span className="text-ink-3">(optional)</span>
            </span>
            <Input type="url" inputMode="url" value={link} onChange={(e) => setLink(e.target.value)} maxLength={500} placeholder="https://meet.google.com/abc-defg-hij" />
            <span className="mt-1 block text-meta text-ink-3">When it&apos;s online: a Join button shows on the calendar and in your to do.</span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">
              Products to discuss <span className="text-ink-3">(optional)</span>
            </span>
            <Combobox
              mode="multiple"
              className="w-full"
              value={picked}
              onChange={setPicked}
              options={products ?? []}
              loading={!products}
              showSearch={{ optionFilterProp: "label" }}
              placeholder="Type a product"
              notFoundContent={<p className="px-1 py-3 text-center text-meta text-ink-3">No product by that name. Products are added under Catalogue → Products.</p>}
            />
          </label>
          <FormError message={error} />
        </div>
      </Modal>
    </>
  );
}

/**
 * Ticking off a planned call: what came of it, and the products actually
 * discussed (those planned are filled in to start).
 */
export function CallOutcome({
  open,
  planned,
  onCancel,
  onSave,
  saving,
}: {
  open: boolean;
  planned: { code: string; name: string }[];
  onCancel: () => void;
  onSave: (outcome: string, discussed: string[]) => void;
  saving: boolean;
}) {
  const [outcome, setOutcome] = useState("");
  const [discussed, setDiscussed] = useState(planned.map((p) => p.code));
  const [options, setOptions] = useState<Option[]>(planned.map((p) => ({ value: p.code, label: p.name })));
  const [, start] = useTransition();
  return (
    <Modal
      open={open}
      title="Call outcome"
      onCancel={onCancel}
      onOk={() => onSave(outcome.trim(), discussed)}
      okText="Mark done"
      confirmLoading={saving}
      afterOpenChange={(shown) => shown && start(async () => {
        const all = (await callChoices()).products;
        setOptions([...options, ...all.filter((o) => !options.some((p) => p.value === o.value))]);
      })}
      destroyOnHidden
    >
      <div className="space-y-4 pt-1">
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Outcome</span>
          <Textarea rows={3} value={outcome} onChange={(e) => setOutcome(e.target.value)} maxLength={5000} placeholder="e.g. Interested; wants samples next week" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Products discussed</span>
          <Combobox mode="multiple" className="w-full" value={discussed} onChange={setDiscussed} options={options} showSearch={{ optionFilterProp: "label" }} />
        </label>
      </div>
    </Modal>
  );
}
