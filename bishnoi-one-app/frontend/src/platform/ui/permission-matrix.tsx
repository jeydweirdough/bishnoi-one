"use client";

import { TextButton } from "./button";

// What a role may do, in one grid for every app (2026-11-04): a row for each area of the app, a column for each standard
// action (Create, Read, Update, Delete / Submit, Approve, Reject, Return, Cancel, Reopen / Import, Export, Print, Assign,
// Transfer, Post, Void), and what an app offers that isn't one of those as switches at the row's end. Only the columns
// the app has are drawn. The app still names and enforces each permission; this only lays them out the same way.

export type MatrixAction = { key: string; label: string; permission: string; standard?: string | null; kind?: string };
export type MatrixArea = { key: string; name: string; group: string; actions: MatrixAction[] };

const GROUPS = [
  { kind: "crud", label: "Records", columns: ["create", "read", "update", "delete"] },
  { kind: "workflow", label: "Process", columns: ["submit", "approve", "reject", "return", "cancel", "reopen"] },
  { kind: "special", label: "Special", columns: ["import", "export", "print", "assign", "transfer", "post", "void"] },
] as const;

const title = (word: string) => word.charAt(0).toUpperCase() + word.slice(1);

export function PermissionMatrix({
  catalogue,
  granted,
  locked = false,
  onChange,
}: {
  catalogue: MatrixArea[];
  granted: string[];
  locked?: boolean;
  onChange: (permissions: string[]) => void;
}) {
  const has = new Set(granted);
  const offered = new Set(catalogue.flatMap((a) => a.actions.map((x) => x.standard).filter(Boolean) as string[]));
  const columns = GROUPS.map((g) => ({ ...g, columns: g.columns.filter((c) => offered.has(c)) })).filter((g) => g.columns.length > 0);
  const hasOther = catalogue.some((a) => a.actions.some((x) => !x.standard));
  const areaGroups = [...new Set(catalogue.map((a) => a.group))];

  const cell = (area: MatrixArea, standard: string) => area.actions.find((a) => a.standard === standard);
  const readOf = (area: MatrixArea) => cell(area, "read")?.permission;

  function toggle(area: MatrixArea, permission: string, on: boolean) {
    const next = new Set(has);
    const read = readOf(area);
    if (on) {
      next.add(permission);
      // Doing anything in an area starts with seeing it.
      if (read) next.add(read);
    } else {
      next.delete(permission);
      // Without seeing an area there's nothing in it to do.
      if (permission === read) for (const a of area.actions) next.delete(a.permission);
    }
    onChange([...next].sort());
  }

  function all(area: MatrixArea, on: boolean) {
    const next = new Set(has);
    for (const a of area.actions) (on ? next.add(a.permission) : next.delete(a.permission));
    onChange([...next].sort());
  }

  function column(standard: string, on: boolean) {
    const next = new Set(has);
    for (const area of catalogue) {
      const a = cell(area, standard);
      if (!a) continue;
      if (on) {
        next.add(a.permission);
        const read = readOf(area);
        if (read) next.add(read);
      } else {
        next.delete(a.permission);
        if (standard === "read") for (const x of area.actions) next.delete(x.permission);
      }
    }
    onChange([...next].sort());
  }

  const span = 1 + columns.reduce((n, g) => n + g.columns.length, 0) + (hasOther ? 1 : 0) + (locked ? 0 : 1);

  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full min-w-max text-sm">
        <thead>
          <tr className="text-caps text-ink-3 uppercase">
            <th scope="col" className="sticky left-0 bg-sheet py-1.5 pr-4 text-left font-medium" rowSpan={2}>
              Area
            </th>
            {columns.map((g) => (
              <th key={g.kind} scope="colgroup" colSpan={g.columns.length} className="border-l border-rule px-2 pb-1 text-center font-medium">
                {g.label}
              </th>
            ))}
            {hasOther && (
              <th scope="col" rowSpan={2} className="border-l border-rule px-3 text-left font-medium">
                Other
              </th>
            )}
            {!locked && <th scope="col" rowSpan={2} className="w-12" />}
          </tr>
          <tr className="text-meta text-ink-2">
            {columns.map((g) =>
              g.columns.map((c, i) => {
                const rows = catalogue.map((a) => cell(a, c)).filter(Boolean) as MatrixAction[];
                const every = rows.length > 0 && rows.every((a) => has.has(a.permission));
                return (
                  <th key={c} scope="col" className={`px-1.5 pb-1.5 text-center font-medium ${i === 0 ? "border-l border-rule" : ""}`}>
                    {locked ? (
                      title(c)
                    ) : (
                      <TextButton onClick={() => column(c, !every)} title={every ? `Take ${title(c)} from every area` : `Give ${title(c)} in every area`}>
                        {title(c)}
                      </TextButton>
                    )}
                  </th>
                );
              }),
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {areaGroups.map((group) => (
            <GroupRows key={group} group={group} areas={catalogue.filter((a) => a.group === group)} />
          ))}
        </tbody>
      </table>
    </div>
  );

  function GroupRows({ group, areas }: { group: string; areas: MatrixArea[] }) {
    return (
      <>
        {areaGroups.length > 1 && (
          <tr>
            <th scope="rowgroup" colSpan={span} className="sticky left-0 bg-bench px-2 py-1 text-left text-caps font-medium text-ink-3 uppercase">
              {group}
            </th>
          </tr>
        )}
        {areas.map((area) => {
          const every = area.actions.every((a) => has.has(a.permission));
          return (
            <tr key={area.key} className="hover:bg-bench/50">
              <th scope="row" className="sticky left-0 bg-sheet py-2 pr-4 text-left font-normal text-ink">
                {area.name}
              </th>
              {columns.map((g) =>
                g.columns.map((c, i) => {
                  const a = cell(area, c);
                  return (
                    <td key={c} className={`px-1.5 py-2 text-center ${i === 0 ? "border-l border-rule" : ""}`}>
                      {a ? (
                        <input
                          suppressHydrationWarning
                          type="checkbox"
                          disabled={locked}
                          checked={has.has(a.permission)}
                          onChange={(e) => toggle(area, a.permission, e.target.checked)}
                          aria-label={`${area.name}: ${a.label}`}
                          title={a.label}
                          className="size-4 cursor-pointer accent-hema disabled:cursor-not-allowed"
                        />
                      ) : (
                        <span className="text-ink-3" aria-hidden>
                          ·
                        </span>
                      )}
                    </td>
                  );
                }),
              )}
              {hasOther && (
                <td className="border-l border-rule px-3 py-2">
                  <div className="flex flex-wrap gap-1.5">
                    {area.actions
                      .filter((a) => !a.standard)
                      .map((a) => {
                        const on = has.has(a.permission);
                        return (
                          <button
                            suppressHydrationWarning
                            key={a.permission}
                            type="button"
                            disabled={locked}
                            aria-pressed={on}
                            onClick={() => toggle(area, a.permission, !on)}
                            className={`rounded-md border px-2 py-0.5 text-meta transition-colors ${on ? "border-sage-deep bg-mint-2 font-semibold text-ink" : "border-rule-strong bg-sheet text-ink-3 hover:border-sage-deep"}`}
                          >
                            {a.label}
                          </button>
                        );
                      })}
                  </div>
                </td>
              )}
              {!locked && (
                <td className="py-2 text-right">
                  {area.actions.length > 1 && (
                    <TextButton onClick={() => all(area, !every)}>{every ? "None" : "All"}</TextButton>
                  )}
                </td>
              )}
            </tr>
          );
        })}
      </>
    );
  }
}
