"use client";

import { AppWindow, Mail, Network, Power, PowerOff, Trash2 } from "lucide-react";
import { useState } from "react";
import { BulkBar, BulkStep, useBulkRun, useSelection } from "@/src/platform/bulk/selection";
import { plural } from "@/src/platform/lib/format";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, Select } from "@/src/platform/ui/field";
import { Combobox } from "@/src/platform/ui/pickers";
import { bulkDeletePeople, bulkGiveModule, bulkInvitePeople, bulkSetManager, bulkSwitchPeople } from "./actions";
import { moduleLabel } from "./labels";
import type { AccessData } from "./types";

const NOUN: [string, string] = ["employee", "employees"];

/** What can be done to several employees at once (2026-11-01): the bar under the list once some are ticked. */
export function EmployeesBulk({ data }: { data: AccessData }) {
  const s = useSelection();
  const { run, running } = useBulkRun();
  const [giving, setGiving] = useState(false);
  const [managing, setManaging] = useState(false);
  const [manager, setManager] = useState<string | undefined>();
  const many = plural(s.ids.length, ...NOUN);
  const did = (what: string) => (n: number) => `${plural(n, ...NOUN)} ${what}`;

  const step = managing ? (
    <BulkStep
      submitLabel={manager ? `Report to them` : "Clear their manager"}
      onCancel={() => (setManaging(false), setManager(undefined))}
      onSubmit={async () => {
        await run({ doing: manager ? "Setting the manager" : "Clearing the manager", did: did(manager ? "now report to them" : "have no manager") }, (ids) => bulkSetManager(ids, manager ?? null));
      }}
    >
      <Field label="Reports to" className="w-64">
        {() => (
          <Combobox
            allowClear
            placeholder="Choose an employee (empty clears it)"
            options={data.people.filter((p) => p.status === "active").map((p) => ({ value: p.id, label: p.fullName }))}
            value={manager}
            onChange={(v) => setManager((v as string | undefined) ?? undefined)}
          />
        )}
      </Field>
    </BulkStep>
  ) : giving ? (
    <BulkStep
      submitLabel={`Give to ${many}`}
      onCancel={() => setGiving(false)}
      onSubmit={async (form) => {
        const key = String(form.get("app") ?? "");
        await run({ doing: "Giving the app", did: did("given it") }, (ids) => bulkGiveModule(key, ids));
      }}
    >
      <Field label="App" className="w-56">
        {(p) => (
          <Select {...p} name="app" defaultValue={data.modules[0]?.key}>
            {data.modules.map((m) => (
              <option key={m.key} value={m.key}>
                {moduleLabel(m)}
              </option>
            ))}
          </Select>
        )}
      </Field>
    </BulkStep>
  ) : undefined;

  return (
    <BulkBar noun={NOUN} step={step}>
      <Button size="sm" icon={<Network className="size-4" aria-hidden />} disabled={running} onClick={() => setManaging(true)}>
        Set manager
      </Button>
      <Button size="sm" icon={<AppWindow className="size-4" aria-hidden />} disabled={running} onClick={() => setGiving(true)}>
        Give an app
      </Button>
      <Button size="sm" icon={<Mail className="size-4" aria-hidden />} disabled={running} onClick={() => void run({ doing: "Sending invitations", did: did("invited") }, bulkInvitePeople)}>
        Send invitation
      </Button>
      <Button size="sm" icon={<Power className="size-4" aria-hidden />} disabled={running} onClick={() => void run({ doing: "Switching on", did: did("switched on") }, (ids) => bulkSwitchPeople("active", ids))}>
        Switch on
      </Button>
      <ConfirmButton
        label="Switch off"
        icon={<PowerOff className="size-4" aria-hidden />}
        title={`Switch off ${many}?`}
        body="They can't sign in to any app until switched on again."
        confirmLabel="Switch off"
        triggerSize="sm"
        disabled={running}
        onConfirm={async () => void (await run({ doing: "Switching off", did: did("switched off") }, (ids) => bulkSwitchPeople("suspended", ids)))}
      />
      <ConfirmButton
        label="Delete"
        icon={<Trash2 className="size-4" aria-hidden />}
        title={`Delete ${many}?`}
        body="They go to the recycle bin: switched off and signed out everywhere. You can restore them from there."
        confirmLabel="Delete"
        triggerSize="sm"
        triggerVariant="danger"
        disabled={running}
        onConfirm={async () => void (await run({ doing: "Deleting", did: did("moved to the recycle bin") }, bulkDeletePeople))}
      />
    </BulkBar>
  );
}
