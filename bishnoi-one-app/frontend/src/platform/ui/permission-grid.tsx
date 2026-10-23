"use client";

import { TextButton } from "./button";

/** One area of a module's screens, and what a role can be allowed in it (from the module's API). */
export type PermissionArea = {
  key: string;
  name: string;
  group: string;
  actions: { key: string; label: string; permission: string }[];
};

/**
 * The permission grid: each area of a module, by group, and a switch for each
 * thing it can allow. Seeing an area comes with doing anything in it; taking
 * away seeing takes the rest. Used by every roles screen (a module's, and the
 * Platform's for every module), so it's fixed here, not in a screen.
 */
export function PermissionGrid({
  catalogue,
  granted,
  locked = false,
  onChange,
}: {
  catalogue: PermissionArea[];
  granted: string[];
  locked?: boolean;
  onChange: (permissions: string[]) => void;
}) {
  const has = new Set(granted);
  const groups = [...new Set(catalogue.map((a) => a.group))];

  function toggle(area: PermissionArea, permission: string, on: boolean) {
    const next = new Set(has);
    const view = `${area.key}.view`;
    const hasView = area.actions.some((a) => a.permission === view);
    if (on) {
      next.add(permission);
      // Doing anything in an area starts with seeing it.
      if (hasView) next.add(view);
    } else {
      next.delete(permission);
      // Without seeing an area there's nothing in it to create, edit or delete.
      if (permission === view) for (const a of area.actions) next.delete(a.permission);
    }
    onChange([...next].sort());
  }

  function all(area: PermissionArea, on: boolean) {
    const next = new Set(has);
    for (const a of area.actions) {
      if (on) next.add(a.permission);
      else next.delete(a.permission);
    }
    onChange([...next].sort());
  }

  return (
    <>
      {groups.map((group) => (
        <div key={group} className="mt-4">
          <h3 className="text-caps text-ink-3 uppercase">{group}</h3>
          <ul className="mt-1 divide-y divide-rule">
            {catalogue
              .filter((a) => a.group === group)
              .map((area) => {
                const every = area.actions.every((a) => has.has(a.permission));
                return (
                  <li key={area.key} className="grid gap-2 py-2.5 md:grid-cols-[15rem_minmax(0,1fr)] md:items-center">
                    <div className="flex items-center justify-between gap-2 text-sm">
                      <span className="min-w-0 text-ink">{area.name}</span>
                      {!locked && area.actions.length > 1 && (
                        <TextButton onClick={() => all(area, !every)} className="shrink-0 md:hidden">
                          {every ? "None" : "All"}
                        </TextButton>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {area.actions.map((a) => {
                        const on = has.has(a.permission);
                        return (
                          <label
                            key={a.permission}
                            className={`relative inline-flex items-center rounded-md border px-3 py-1 text-meta transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-hema ${
                              on ? "border-hema bg-hema-tint font-semibold text-ink" : "border-rule-strong bg-sheet text-ink-2"
                            } ${locked ? "cursor-default" : "cursor-pointer hover:border-hema"}`}
                          >
                            <input
                              type="checkbox"
                              className="sr-only"
                              checked={on}
                              disabled={locked}
                              onChange={(e) => toggle(area, a.permission, e.target.checked)}
                            />
                            {a.label}
                          </label>
                        );
                      })}
                      {!locked && area.actions.length > 1 && (
                        <TextButton onClick={() => all(area, !every)} className="ml-1 hidden md:inline">
                          {every ? "None" : "All"}
                        </TextButton>
                      )}
                    </div>
                  </li>
                );
              })}
          </ul>
        </div>
      ))}
    </>
  );
}
