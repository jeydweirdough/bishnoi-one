"use client";

import { InputNumber } from "antd";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Sheet } from "@/src/platform/ui/sheet";
import { saveRetentionWindows, type RetentionWindows } from "../../actions/settings";

type Team = RetentionWindows["teams"][number];

function DepartmentRow({ team, company, onSaved }: { team: Team; company: RetentionWindows["company"]; onSaved: (w: RetentionWindows) => void }) {
  const [atRisk, setAtRisk] = useState(team.atRiskDays ?? company.atRiskDays);
  const [lost, setLost] = useState(team.lostDays ?? company.lostDays);
  const [pending, start] = useTransition();
  const dirty = !team.own || atRisk !== team.atRiskDays || lost !== team.lostDays;
  function save(w: { atRiskDays: number | null; lostDays: number | null }, done: string) {
    start(async () => {
      const r = await saveRetentionWindows(team.id, w);
      if (!r.ok) return void toast.error(r.error);
      toast.success(done);
      onSaved(r.data);
    });
  }
  return (
    <Sheet className="px-5 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="font-semibold text-ink">
          {team.name}
          <span className="ml-2 text-meta font-normal text-ink-3">{team.own ? "Its own windows" : "Uses the company's"}</span>
        </h2>
        {team.own && (
          <Button size="sm" variant="quiet" onClick={() => save({ atRiskDays: null, lostDays: null }, "Back to the company's")} disabled={pending}>
            Use the company&apos;s
          </Button>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-sm text-ink">At risk after</span>
          <span className="flex items-center gap-2">
            <InputNumber min={1} max={3650} value={atRisk} onChange={(n) => setAtRisk(n ?? atRisk)} className="w-24" />
            <span className="text-meta text-ink-3">days without a quote</span>
          </span>
        </label>
        <label className="block">
          <span className="mb-1 block text-sm text-ink">Lost after</span>
          <span className="flex items-center gap-2">
            <InputNumber min={1} max={3650} value={lost} onChange={(n) => setLost(n ?? lost)} className="w-24" />
            <span className="text-meta text-ink-3">days without a quote</span>
          </span>
        </label>
      </div>
      <div className="mt-4">
        <Button variant="primary" onClick={() => save({ atRiskDays: atRisk, lostDays: lost }, "Saved")} loading={pending} disabled={!dirty}>
          {team.own ? "Save" : "Give it its own"}
        </Button>
      </div>
    </Sheet>
  );
}

/** Settings → Retention windows: the company's, and each department's own (a manager's: theirs). */
export function RetentionWindowsEditor({ initial }: { initial: RetentionWindows }) {
  const [w, setW] = useState(initial);
  return (
    <div className="max-w-3xl space-y-4">
      <Sheet className="px-5 py-4">
        <h2 className="font-semibold text-ink">The company&apos;s</h2>
        <p className="mt-1 text-ink-2">
          At risk after {w.company.atRiskDays} days without a quote, lost after {w.company.lostDays}. An administrator changes these under Pricing and retention.
        </p>
      </Sheet>
      {w.teams.length === 0 ? (
        <p className="text-ink-3">No departments to set yet.</p>
      ) : (
        w.teams.map((t) => <DepartmentRow key={t.id + JSON.stringify(t)} team={t} company={w.company} onSaved={setW} />)
      )}
    </div>
  );
}
