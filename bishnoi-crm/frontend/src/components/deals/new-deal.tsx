"use client";

import { Modal, Select } from "antd";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { Button } from "@/src/platform/ui/button";
import { findCustomers } from "../../actions/deals";

type Option = { value: string; label: string };

/** Which customer the deal is with: an Ant select that searches as you type. */
function CustomerPicker({ value, onChange, autoFocus }: { value: string | null; onChange: (id: string | null) => void; autoFocus?: boolean }) {
  const [options, setOptions] = useState<Option[]>([]);
  const [loading, start] = useTransition();
  const seq = useRef(0);

  function search(q: string) {
    const mine = ++seq.current;
    start(async () => {
      const found = await findCustomers(q).catch(() => []);
      // Only the latest search's answer counts.
      if (mine === seq.current) setOptions(found.map((c) => ({ value: c.id, label: c.city ? `${c.name} · ${c.city}` : c.name })));
    });
  }

  useEffect(() => search(""), []);

  return (
    <Select
      showSearch={{ filterOption: false, onSearch: search }}
      autoFocus={autoFocus}
      value={value}
      onChange={(v) => onChange(v ?? null)}
      options={options}
      loading={loading}
      placeholder="Type a customer's name"
      notFoundContent={loading ? "Looking…" : "No customer by that name"}
      className="w-full"
      size="large"
      allowClear
    />
  );
}

/** "New deal": asks which customer in a modal, then opens the deal form for them. */
export function NewDealButton({ variant = "primary", label = "New deal" }: { variant?: "primary" | "default"; label?: string }) {
  const [open, setOpen] = useState(false);
  const [customer, setCustomer] = useState<string | null>(null);
  const router = useRouter();
  const go = () => customer && router.push(`/deals/new?company=${encodeURIComponent(customer)}`);
  return (
    <>
      <Button variant={variant} icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)} aria-haspopup="dialog">
        {label}
      </Button>
      <Modal
        open={open}
        title="New deal"
        onCancel={() => setOpen(false)}
        onOk={go}
        okText="Continue"
        okButtonProps={{ disabled: !customer }}
        width={460}
        destroyOnHidden
      >
        <p className="mb-3 text-sm text-ink-2">A deal is with a customer. Which one?</p>
        <CustomerPicker value={customer} onChange={setCustomer} autoFocus />
      </Modal>
    </>
  );
}

/** The same question on a page of its own, for /deals/new with no customer given. */
export function CustomerStep() {
  const [customer, setCustomer] = useState<string | null>(null);
  const router = useRouter();
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1">
        <CustomerPicker value={customer} onChange={setCustomer} autoFocus />
      </div>
      <Button variant="primary" disabled={!customer} onClick={() => customer && router.push(`/deals/new?company=${encodeURIComponent(customer)}`)}>
        Continue
      </Button>
    </div>
  );
}
