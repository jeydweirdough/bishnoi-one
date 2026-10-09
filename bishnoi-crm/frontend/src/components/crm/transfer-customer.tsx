"use client";

import { Input } from "@/src/platform/ui/field";
import { Alert, Modal } from "antd";
import { ArrowLeftRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { findTransferPerson, transferCustomer, type TransferPerson } from "../../actions/crm";

/**
 * Transfer, beside the customer's owner: the new owner is named by their
 * employee ID, typed, then shown by name before anything moves. The ID is
 * the safeguard: nobody hands a customer to the wrong person from a list.
 */
export function TransferCustomer({ companyId, companyName }: { companyId: string; companyName: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [person, setPerson] = useState<TransferPerson | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function close() {
    setOpen(false);
    setCode("");
    setPerson(null);
    setError(null);
  }

  function find() {
    if (!code.trim()) return setError("Type their employee ID.");
    start(async () => {
      const r = await findTransferPerson(companyId, code);
      if (r.ok) {
        setPerson(r.data);
        setError(null);
      } else {
        setPerson(null);
        setError(r.fields?.employeeId ?? r.error);
      }
    });
  }

  function transfer() {
    if (!person) return;
    start(async () => {
      const r = await transferCustomer(companyId, person.employeeId);
      if (!r.ok) {
        setError(r.fields?.employeeId ?? r.error);
        return;
      }
      const { moved } = r.data;
      const extra = [moved.contacts && `${moved.contacts} contact${moved.contacts === 1 ? "" : "s"}`, moved.deals && `${moved.deals} open deal${moved.deals === 1 ? "" : "s"}`]
        .filter(Boolean)
        .join(" and ");
      toast.success(`${companyName} is now ${r.data.to.name}'s`, { description: extra ? `With ${extra}.` : undefined });
      close();
      // Out of reach now: back to the customers this person still has.
      if (!r.data.stillYours) router.push("/companies");
    });
  }

  return (
    <>
      <Button size="sm" icon={<ArrowLeftRight className="size-3.5" aria-hidden />} onClick={() => setOpen(true)} aria-haspopup="dialog">
        Transfer
      </Button>
      <Modal
        open={open}
        title="Transfer customer"
        onCancel={close}
        width={460}
        destroyOnHidden
        footer={
          person ? (
            <div className="flex justify-end gap-2">
              <Button onClick={() => setPerson(null)} disabled={pending}>
                Back
              </Button>
              <Button variant="primary" onClick={transfer} loading={pending}>
                Transfer to {person.name}
              </Button>
            </div>
          ) : (
            <div className="flex justify-end gap-2">
              <Button onClick={close}>Cancel</Button>
              <Button variant="primary" onClick={find} loading={pending} disabled={!code.trim()}>
                Find
              </Button>
            </div>
          )
        }
      >
        {person ? (
          <div className="space-y-3">
            <div className="rounded-sheet border border-rule px-4 py-3">
              <p className="font-medium text-ink">{person.name}</p>
              <p className="text-meta text-ink-3">
                {person.employeeId} · {person.role}
                {person.team && ` · ${person.team.name}`}
              </p>
            </div>
            <p className="text-sm text-ink-2">
              {companyName} goes to them, with the contacts and open deals its current owner has there. Quotes and history stay as they are.
            </p>
            {error && <Alert type="error" showIcon title={error} />}
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-ink-2">Type the employee ID of the salesperson who takes {companyName} over.</p>
            <Input
              autoFocus
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                setError(null);
              }}
              onPressEnter={find}
              placeholder="e.g. EMP-0012"
              maxLength={20}
              status={error ? "error" : undefined}
              aria-label="Employee ID"
            />
            {error && <p className="text-meta text-danger">{error}</p>}
          </div>
        )}
      </Modal>
    </>
  );
}
