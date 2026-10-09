"use client";

import { Modal, Switch } from "antd";
import { Share2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { customerSharing, setCustomerSharing, type Sharing } from "../../actions/sharing";

/**
 * "Customer sharing": whether each division's customers show to the other
 * divisions, for the administrator (every division) and a manager (the
 * divisions they manage). Shown: when someone elsewhere adds a customer with
 * the same name, email or phone, they're told it exists (by name and division,
 * never its details), and a field pointing at a customer can pick it.
 */
export function CustomerSharingButton() {
  const [open, setOpen] = useState(false);
  const [teams, setTeams] = useState<Sharing[] | null>(null);
  const [busy, start] = useTransition();

  function show() {
    setOpen(true);
    start(async () => setTeams(await customerSharing()));
  }

  function flip(t: Sharing, share: boolean) {
    start(async () => {
      const r = await setCustomerSharing(t.id, share);
      if (!r.ok) return void toast.error("Not changed", { description: r.error });
      setTeams((all) => (all ?? []).map((x) => (x.id === t.id ? r.data : x)));
      toast.success(share ? `${t.name}'s customers show to other divisions` : `${t.name}'s customers are kept to ${t.name}`);
    });
  }

  return (
    <>
      <Button icon={<Share2 className="size-4" aria-hidden />} onClick={show}>
        Customer sharing
      </Button>
      <Modal open={open} title="Customer sharing" onCancel={() => setOpen(false)} footer={null} width={560}>
        <p className="text-sm text-ink-2">
          Whether other divisions are told a customer is already here when they add the same one, and can pick it as a hospital or other linked customer. They only
          ever see its name and division, never its details.
        </p>
        <div className="mt-5 rounded-[18px] border border-rule">
          {teams === null ? (
            <p className="px-4 py-4 text-meta text-ink-3">Getting your divisions…</p>
          ) : teams.length === 0 ? (
            <p className="px-4 py-4 text-meta text-ink-3">You don&apos;t manage a division. The administrator sets this for each one.</p>
          ) : (
            <ul className="divide-y divide-rule">
              {teams.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-4 px-4 py-3">
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink">{t.name}</span>
                    <span className="block text-meta text-ink-3">{t.shareCustomers ? "Shown to other divisions, by name" : `Kept to ${t.name}: other divisions don't see them`}</span>
                  </span>
                  <Switch checked={t.shareCustomers} onChange={(v) => flip(t, v)} loading={busy} aria-label={`Show ${t.name}'s customers to other divisions`} />
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="mt-3 text-meta text-ink-3">People in the division, and anyone whose role reaches it, always see its customers.</p>
        <div className="dialog-actions">
          <Button onClick={() => setOpen(false)}>Done</Button>
        </div>
      </Modal>
    </>
  );
}
