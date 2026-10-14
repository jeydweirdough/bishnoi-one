"use client";

import { Segmented } from "antd";
import { Combobox } from "@/src/platform/ui/pickers";
import { useState } from "react";

/** A team something can be for (Settings → Forms and Customer types). */
export type TeamName = { id: string; name: string; isActive: boolean };

type Whose = "everyone" | "only" | "except";

/** "Everyone", "Only STC, URO" or "All except B2C": who something is for, in words. */
export function teamsSummary(teams: TeamName[], only: string[] = [], except: string[] = []): string {
  const names = (ids: string[]) => ids.map((id) => teams.find((t) => t.id === id)?.name ?? "a removed team").join(", ");
  if (only.length) return `Only ${names(only)}`;
  if (except.length) return `All except ${names(except)}`;
  return "Everyone";
}

/**
 * Who something is for: everyone, only some teams (the Rx team's own fields
 * and types), or everyone but some. A customer's team is its owner's.
 */
export function TeamsFor({
  teams,
  only = [],
  except = [],
  onChange,
  what = "it",
  notes,
}: {
  teams: TeamName[];
  only?: string[];
  except?: string[];
  onChange: (only: string[], except: string[]) => void;
  /** What's being set, for the note under it ("this field", "this type"). */
  what?: string;
  /** Other notes and placeholder, when what's picked isn't teams (customer types). */
  notes?: { everyone: string; only: string; except: string; placeholder: string };
}) {
  const [mode, setMode] = useState<Whose>(only.length ? "only" : except.length ? "except" : "everyone");
  const picked = mode === "only" ? only : mode === "except" ? except : [];
  const set = (m: Whose, ids: string[]) => (m === "everyone" ? onChange([], []) : m === "only" ? onChange(ids, []) : onChange([], ids));
  return (
    <div className="space-y-2">
      <Segmented<Whose>
        size="small"
        block
        value={mode}
        onChange={(m) => {
          setMode(m);
          // The teams already picked carry over; "Everyone" clears them.
          set(m, [...only, ...except]);
        }}
        options={[
          { value: "everyone", label: "Everyone" },
          { value: "only", label: "Only" },
          { value: "except", label: "All except" },
        ]}
      />
      {mode !== "everyone" && (
        <Combobox
          mode="multiple"
          className="w-full"
          value={picked}
          onChange={(ids) => set(mode, ids)}
          placeholder={notes?.placeholder ?? "Select teams"}
          options={teams.filter((t) => t.isActive || picked.includes(t.id)).map((t) => ({ value: t.id, label: t.name }))}
          showSearch={{ optionFilterProp: "label" }}
        />
      )}
      <p className="text-meta text-ink-3">
        {notes
          ? notes[mode]
          : mode === "only"
          ? `Only customers assigned to someone in these teams get ${what}.`
          : mode === "except"
            ? `Customers assigned to someone in these teams don't get ${what}.`
            : `Every customer gets ${what}.`}
      </p>
    </div>
  );
}
