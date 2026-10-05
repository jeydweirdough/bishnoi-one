"use client";

import { DatePicker, Input, Modal, Select } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { PhoneCall } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { FormError } from "@/src/platform/ui/field";
import { callChoices, createActivity } from "../../actions/crm";
import { findCustomers } from "../../actions/deals";

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
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function show() {
    setOpen(true);
    if (!products) start(async () => setProducts((await callChoices()).products));
    if (!customer) search("");
  }

  function search(q: string) {
    start(async () => setCustomers((await findCustomers(q)).map((c) => ({ value: c.id, label: c.city ? `${c.name} · ${c.city}` : c.name }))));
  }

  function save() {
    if (!companyId || !when || !objective.trim()) return setError("Pick who it's with and when, and say what it's for.");
    start(async () => {
      const r = await createActivity({
        kind: "meeting",
        subject: objective.trim(),
        objective: objective.trim(),
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
      toast.success("Call planned", { description: `${when.format("ddd D MMM, h:mm A")}: ${objective.trim()}` });
      setOpen(false);
      setObjective("");
      setPicked([]);
      setError(null);
    });
  }

  return (
    <>
      <Button variant={variant} icon={<PhoneCall className="size-4" aria-hidden />} onClick={show}>
        New call
      </Button>
      <Modal open={open} title="New call" onCancel={() => setOpen(false)} onOk={save} okText="Plan the call" confirmLoading={pending} width={520} destroyOnHidden>
        <div className="space-y-4 pt-1">
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Who it&apos;s with</span>
            <Select
              className="w-full"
              value={companyId || undefined}
              onChange={setCompanyId}
              options={customers}
              disabled={Boolean(customer)}
              showSearch={{ filterOption: false, onSearch: search }}
              placeholder="Type a customer's name"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">When</span>
            <DatePicker className="w-full" showTime={{ format: "h:mm A", minuteStep: 15 }} format="ddd D MMM YYYY, h:mm A" value={when} onChange={setWhen} />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Objective</span>
            <Input value={objective} onChange={(e) => setObjective(e.target.value)} maxLength={300} placeholder="e.g. Get Onco One on their formulary" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">
              Products to discuss <span className="text-ink-3">(optional)</span>
            </span>
            <Select
              mode="multiple"
              className="w-full"
              value={picked}
              onChange={setPicked}
              options={products ?? []}
              loading={!products}
              showSearch={{ optionFilterProp: "label" }}
              placeholder="Type a product"
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
      title="How did it go?"
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
          <span className="mb-1.5 block text-sm text-ink">What came of it</span>
          <Input.TextArea rows={3} value={outcome} onChange={(e) => setOutcome(e.target.value)} maxLength={5000} placeholder="e.g. Interested; wants samples next week" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Products discussed</span>
          <Select mode="multiple" className="w-full" value={discussed} onChange={setDiscussed} options={options} showSearch={{ optionFilterProp: "label" }} />
        </label>
      </div>
    </Modal>
  );
}
