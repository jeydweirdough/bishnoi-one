"use client";

import { InputNumber } from "antd";
import { Combobox } from "@/src/platform/ui/pickers";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Sheet } from "@/src/platform/ui/sheet";
import { dropAttentionRule, saveAttentionRule, type AttentionRules, type Rule } from "@/src/modules/crm/actions/settings";

const FIELDS: { key: keyof Omit<Rule, "team">; label: string; unit: string; min: number; max: number }[] = [
  { key: "quietDays", label: "A customer is quiet after", unit: "days with nothing done", min: 1, max: 365 },
  { key: "noticeDays", label: "Birthdays and anniversaries", unit: "days ahead", min: 0, max: 60 },
  { key: "stuckDays", label: "A quote is stuck after waiting", unit: "days for approval", min: 1, max: 60 },
  { key: "clidpDays", label: "A CLIDP running out within", unit: "days (B2B and BID)", min: 1, max: 365 },
];

function RuleRow({ rule, teamId, onSaved, onDrop, readOnly }: { rule: Rule; teamId: string | null; onSaved: (r: AttentionRules) => void; onDrop?: () => void; readOnly?: boolean }) {
  const [v, setV] = useState(rule);
  const [pending, start] = useTransition();
  const dirty = FIELDS.some((f) => v[f.key] !== rule[f.key]);
  function save() {
    start(async () => {
      const r = await saveAttentionRule({ teamId, quietDays: v.quietDays, noticeDays: v.noticeDays, clidpDays: v.clidpDays, stuckDays: v.stuckDays });
      if (!r.ok) return void toast.error(r.error);
      toast.success("Saved");
      onSaved(r.data);
    });
  }
  return (
    <Sheet className="px-5 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="font-semibold text-ink">
          {rule.team ? rule.team.name : "Everyone"}
          {readOnly && <span className="ml-2 text-meta font-normal text-ink-3">The company&apos;s; an administrator changes it</span>}
        </h2>
        {onDrop && (
          <Button size="sm" variant="quiet" onClick={onDrop} disabled={pending}>
            Use everyone&apos;s
          </Button>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            <span className="mb-1 block text-sm text-ink">{f.label}</span>
            <span className="flex items-center gap-2">
              <InputNumber disabled={readOnly} min={f.min} max={f.max} value={v[f.key]} onChange={(n) => setV({ ...v, [f.key]: n ?? rule[f.key] })} className="w-24" />
              <span className="text-meta text-ink-3">{f.unit}</span>
            </span>
          </label>
        ))}
      </div>
      {!readOnly && (
        <div className="mt-4">
          <Button variant="primary" onClick={save} loading={pending} disabled={!dirty}>
            Save
          </Button>
        </div>
      )}
    </Sheet>
  );
}

/** Settings → Attention: when something is worth a prompt on the home page, for everyone and per division. */
export function AttentionRulesEditor({ initial }: { initial: AttentionRules }) {
  const [rules, setRules] = useState(initial);
  const [adding, setAdding] = useState<string | undefined>();
  const [, start] = useTransition();
  const free = rules.teams.filter((t) => !rules.divisions.some((d) => d.team?.id === t.id));
  return (
    <div className="max-w-3xl space-y-4">
      <RuleRow key={JSON.stringify(rules.everyone)} rule={rules.everyone} teamId={null} onSaved={setRules} readOnly={rules.canSetEveryone === false} />
      {rules.divisions.map((d) => (
        <RuleRow
          key={d.team!.id + JSON.stringify(d)}
          rule={d}
          teamId={d.team!.id}
          onSaved={setRules}
          onDrop={() =>
            start(async () => {
              const r = await dropAttentionRule(d.team!.id);
              if (r.ok) setRules(r.data);
              else toast.error(r.error);
            })
          }
        />
      ))}
      {free.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <Combobox className="w-56" placeholder="Select a division" value={adding} onChange={setAdding} options={free.map((t) => ({ value: t.id, label: t.name }))} />
          <Button
            disabled={!adding}
            onClick={() =>
              start(async () => {
                const e = rules.everyone;
                const r = await saveAttentionRule({ teamId: adding!, quietDays: e.quietDays, noticeDays: e.noticeDays, clidpDays: e.clidpDays, stuckDays: e.stuckDays });
                if (!r.ok) return void toast.error(r.error);
                setRules(r.data);
                setAdding(undefined);
              })
            }
          >
            Override for this division
          </Button>
        </div>
      )}
    </div>
  );
}
