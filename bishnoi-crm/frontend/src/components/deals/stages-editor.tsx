"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import type { DealLists, DealStage, ForecastCategory } from "@/src/platform/lib/types";
import { deleteDealStage, saveDealLists, saveDealStage, type DealStageChange } from "../../actions/deals";
import { CATEGORY_LABELS, OPEN_CATEGORIES } from "./words";

type OpenCategory = Exclude<ForecastCategory, "closed">;
const cell = "h-9 border-0 border-b border-control bg-transparent text-sm focus:border-hema focus:outline-none";

/** The deal stages: add, rename, reorder, set their probability and forecast, switch off, delete an unused one. */
export function DealStagesEditor({ stages }: { stages: DealStage[] }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [name, setName] = useState("");
  const [probability, setProbability] = useState("50");
  const [category, setCategory] = useState<OpenCategory>("pipeline");
  const [fields, setFields] = useState<Record<string, string>>({});
  const open = stages.filter((s) => s.outcome === "open");
  const closed = stages.filter((s) => s.outcome !== "open");

  function save(code: string | null, change: DealStageChange, done: string) {
    start(async () => {
      const result = await saveDealStage(code, change);
      if (!result.ok) {
        if (code) toast.error(Object.values(result.fields ?? {})[0] ?? result.error);
        else setFields(result.fields ?? { name: result.error });
        return;
      }
      if (!code) {
        setName("");
        setFields({});
      }
      toast.success(done);
      router.refresh();
    });
  }

  // Moving swaps places with the neighbour among the open stages.
  function move(i: number, by: -1 | 1) {
    const a = open[i];
    const b = open[i + by];
    start(async () => {
      const first = await saveDealStage(a.code, { sortOrder: b.sortOrder });
      const second = first.ok ? await saveDealStage(b.code, { sortOrder: a.sortOrder }) : first;
      if (!second.ok) toast.error(second.error);
      router.refresh();
    });
  }

  return (
    <div className="space-y-5">
      <Sheet className="px-5 py-4">
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            const p = Number(probability);
            if (!Number.isInteger(p) || p < 0 || p > 100) {
              setFields({ probability: "A whole number from 0 to 100." });
              return;
            }
            save(null, { name: name.trim(), probability: p, forecastCategory: category }, `${name.trim()} added`);
          }}
          className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_7rem_10rem_auto]"
        >
          <Field label="New stage" error={fields.name}>
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Trial order" />}
          </Field>
          <Field label="Probability (%)" error={fields.probability}>
            {(p) => <Input {...p} inputMode="numeric" value={probability} onChange={(e) => setProbability(e.target.value)} />}
          </Field>
          <Field label="Forecast">
            {(p) => (
              <Select {...p} value={category} onChange={(e) => setCategory(e.target.value as OpenCategory)}>
                {OPEN_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Button type="submit" variant="primary" loading={pending} disabled={!name.trim()}>
            Add stage
          </Button>
        </form>
      </Sheet>

      <Sheet>
        <h2 className="border-b border-rule px-5 py-2.5 text-meta font-semibold text-ink-2">Open stages, in order</h2>
        <ul className="divide-y divide-rule">
          {open.map((s, i) => (
            <StageRow key={s.code} stage={s} first={i === 0} last={i === open.length - 1} pending={pending} onSave={(c, d) => save(s.code, c, d)} onMove={(by) => move(i, by)} />
          ))}
        </ul>
        <h2 className="border-y border-rule px-5 py-2.5 text-meta font-semibold text-ink-2">Closing stages: these can be renamed, nothing else</h2>
        <ul className="divide-y divide-rule">
          {closed.map((s) => (
            <StageRow key={s.code} stage={s} first last pending={pending} onSave={(c, d) => save(s.code, c, d)} onMove={() => undefined} />
          ))}
        </ul>
      </Sheet>
    </div>
  );
}

function StageRow({
  stage,
  first,
  last,
  pending,
  onSave,
  onMove,
}: {
  stage: DealStage;
  first: boolean;
  last: boolean;
  pending: boolean;
  onSave: (change: DealStageChange, done: string) => void;
  onMove: (by: -1 | 1) => void;
}) {
  const router = useRouter();
  const [name, setName] = useState(stage.name);
  const [probability, setProbability] = useState(String(stage.probability));
  const isOpen = stage.outcome === "open";
  return (
    <li className={`flex flex-wrap items-center gap-3 px-5 py-3 ${stage.isActive ? "" : "bg-bench/50"}`}>
      {isOpen && (
        <span className="flex flex-col">
          <button type="button" disabled={first || pending} onClick={() => onMove(-1)} className="text-ink-3 hover:text-ink disabled:opacity-30" aria-label={`Move ${stage.name} up`}>
            <ArrowUp className="size-3.5" aria-hidden />
          </button>
          <button type="button" disabled={last || pending} onClick={() => onMove(1)} className="text-ink-3 hover:text-ink disabled:opacity-30" aria-label={`Move ${stage.name} down`}>
            <ArrowDown className="size-3.5" aria-hidden />
          </button>
        </span>
      )}
      <input
        aria-label={`Name of ${stage.name}`}
        value={name}
        onChange={(e) => setName(e.target.value)}
        onBlur={() => name.trim() && name.trim() !== stage.name && onSave({ name: name.trim() }, "Renamed")}
        className={`${cell} min-w-40 flex-1 px-0`}
      />
      {isOpen ? (
        <>
          <label className="flex items-center gap-1.5 text-meta text-ink-3">
            <input
              aria-label={`Probability of ${stage.name}`}
              inputMode="numeric"
              value={probability}
              onChange={(e) => setProbability(e.target.value)}
              onBlur={() => {
                const p = Number(probability);
                if (Number.isInteger(p) && p >= 0 && p <= 100 && p !== stage.probability) onSave({ probability: p }, "Probability changed");
                else setProbability(String(stage.probability));
              }}
              className={`${cell} w-12 px-0 text-right`}
            />
            %
          </label>
          <select
            aria-label={`Forecast of ${stage.name}`}
            value={stage.forecastCategory}
            onChange={(e) => onSave({ forecastCategory: e.target.value as OpenCategory }, "Forecast changed")}
            className={cell}
          >
            {OPEN_CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </>
      ) : (
        <span className="text-meta text-ink-3">
          {stage.probability}% · {CATEGORY_LABELS[stage.forecastCategory]}
        </span>
      )}
      <span className="w-20 text-meta text-ink-3">{stage.deals === 1 ? "1 deal" : `${stage.deals} deals`}</span>
      {isOpen && (
        <Button size="sm" variant="quiet" disabled={pending} onClick={() => onSave({ isActive: !stage.isActive }, stage.isActive ? `${stage.name} switched off` : `${stage.name} switched on`)}>
          {stage.isActive ? "Switch off" : "Switch on"}
        </Button>
      )}
      {isOpen && stage.deals === 0 && (
        <ConfirmButton
          label="Delete"
          triggerSize="sm"
          title={`Delete ${stage.name}?`}
          body="No deal is at this stage, so nothing else changes."
          confirmLabel="Delete stage"
          onConfirm={async () => {
            const result = await deleteDealStage(stage.code);
            if (!result.ok) {
              toast.error(result.error);
              return false;
            }
            toast.success(`${stage.name} deleted`);
            router.refresh();
          }}
        />
      )}
    </li>
  );
}

/** Lead sources and lost reasons: one per line. */
export function DealListsEditor({ lists }: { lists: DealLists }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [sources, setSources] = useState(lists.sources.join("\n"));
  const [reasons, setReasons] = useState(lists.lostReasons.join("\n"));
  const [fields, setFields] = useState<Record<string, string>>({});
  const split = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean);

  return (
    <Sheet className="px-5 py-4">
      <form
        noValidate
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (!split(reasons).length) {
            setFields({ lostReasons: "Keep at least one reason, or a deal couldn't be marked lost." });
            return;
          }
          start(async () => {
            const result = await saveDealLists({ sources: split(sources), lostReasons: split(reasons) });
            if (!result.ok) {
              setFields(result.fields ?? { lostReasons: result.error });
              return;
            }
            setFields({});
            toast.success("Lists saved");
            router.refresh();
          });
        }}
      >
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Lead sources" hint="One per line. Deals already using a removed one keep it." error={fields.sources}>
            {(p) => <Textarea {...p} rows={7} value={sources} onChange={(e) => setSources(e.target.value)} />}
          </Field>
          <Field label="Reasons a deal is lost" hint="One per line. Asked for when a deal is marked lost." error={fields.lostReasons}>
            {(p) => <Textarea {...p} rows={7} value={reasons} onChange={(e) => setReasons(e.target.value)} />}
          </Field>
        </div>
        <Button type="submit" variant="primary" loading={pending}>
          Save lists
        </Button>
      </form>
    </Sheet>
  );
}
